# Backlog: candidate lanes

Candidate lines of work (lanes), ranked by rating, what each moves
(weighted by `docs/direction.md`) and cost. Each entry: source and origin,
mechanism, goal, a rating in words (likely, even or a long shot) with the
evidence for and against, CPU-hour estimate, and its cheapest probe with a
kill-fast rule. `ideas#<n>` names an item in the owner's private idea list.

## Open as lanes

- **act1-content** is owner-led and not a role lane
  (`decision/act1-owner-led`; decisions "act1-content out of the active
  lanes; its jobs run at the default share (owner, 2026-11-12)"): the
  owner builds it in their own sessions on branch `lane/act1-content`; its
  charter is retired, so no lane worker wakes for it, and its jobs run at
  the runner's default share 10. Order and state:
  `lane/act1-content/step` (relics R1, the relic entity, fractional
  amounts, potions P1, discovery and the act1-singles steps landed,
  including the heal relics, Havoc and Infernal Blade; next the remaining
  blocked Ironclad cards C7, C9, C10, C12-C14).
  Reopening it as a role lane is the owner's call.
- **final-round** (`lane/final-round`, project; opened 2026-11-14 as
  the only open lane, `decision/one-lane`): candidate 78 below,
  the owner's final training round (`decision/final-training-round`) at
  A20; cap 135 cpu-h, end 2026-11-22, on-close wake always. Order: A20
  readiness code now; the stall probes 82 and 85 (owner, 2026-11-14:
  prefer the kill; a fix that passes joins the controls, the run's
  self-play and the product); recipe from wide-recipe-confirm's seeds-go;
  A20 controls after the owner's F, V, C2, C3 (or 2026-11-20 12:00);
  seed 201 then replicates 1 and 101; read. Decisions
  "Lane final-round opened".
- **wide-recipe-confirm** (`lane/wide-recipe-confirm`, project): only
  seed 101's read (jobs 1008-1012) is left; it closes at seeds-go with no
  wake and no new lane, and final-round takes the recipe; its step 0
  moved to final-round as optional input 3(a).

**Closed lanes** (outcome and reopen conditions: their decisions entry
"Lane <name> closed" and `measurement/portfolio-<name>`):
- cheap-depth (2026-11-03): line-step adopted; sampled-draw leaf failed.
- two-turn-round (2026-11-03): null on both seeds; the outcome-label
  family closed (ideas#49, the two-turn relabel, parked with it).
- run-decisions (2026-11-04): all three probes null.
- depth-headroom (2026-11-04): no go; the depth family closed.
- cheaper-reads (2026-11-04): matched reads kept as a tool
  (`how/gauntlet-read`); the rest not adopted.
- adaptation-curve (2026-11-04): go; about 100 games to adapt.
- adaptation (2026-11-05): transfer across a mechanic family; ideas#71
  started there.
- goal1-yardstick (2026-11-05): done; the monsters rung's tables recorded.
- difficulty-shift (2026-11-05): both steps failed; the cost is the
  mechanic, not danger.
- boss-cost-two-turn (2026-11-05): stop.
- adapted-two-turn (2026-11-05): go on wins, one burst seed.
- unseen-boss-burst (2026-11-05): fail one turn deep.
- sequential-bursts (2026-11-05): go; bursts compose one turn deep.
- burst-official (2026-11-06): fail; no leak on 0-499, the best burst net fights
  better but its own-pick headline gain pools to +1.09 (0.69).
- crossed-player (2026-11-06): go; +1.60 one turn deep, +1.08 two turns
  deep on the product's decks, clears level.
- pattern-rows-burst (2026-11-06): fail; Hexaghost +0.004 (0.002) pooled
  against the plain twins; the rows show only the next move.
- value-chooser (2026-11-06): go at the bar; level at a sixth of the time,
  as train +4-5 HP and held-out -4 HP.
- runtime-registry (2026-11-06): stages 2-4 landed; stage 5
  (`sparse-state`) specced, not built.
- sparse-state (2026-11-06): go; landed, search +17.6% at 1 thread,
  +35.5% at 16, state 744 bytes, every identity held.
- test-full-memory (2026-11-07): done on memory; the full suite file by
  file peaks at 1.77 GB (was 9.8), test_sweep out of the default run.
- turn-start-leaf (2026-11-07): go; Demon Form decks +7.54 (1.10) HP
  one turn deep with the turn-start leaf, train and other held-out level.
- hands-where-small (2026-11-07): fail; adaptive 16 hands 0.21 (0.13) HP
  per elite, 16 everywhere 0.34 (0.16), no win moved.
- act1-cards-zero-shot (2026-11-07): done; 19 of 22 pack cards level
  one turn deep with @tsl1; Disarm, Impervious, Intimidate cost; Berserk leads.
- yardstick-cards (2026-11-07): done at the cap; games teach Demon Form's
  first tick only (tsl1 gate failed), no composition, two of six power
  modifiers cost @tsl1; their adapted column (read 2026-11-07) closes
  neither @tsl1 cost (`measurement/cards-adapted@stage-a`).
- leaf-blind-numbers (2026-11-07): fail; leftover block mispriced, but
  clearing it at the leaf (@lcb1) moved no card and the cell gauntlet.
- projected-leaf (2026-11-07): fail; @pl2 left inflame-turn1's boss-wins
  cost unmoved, repaired HP only on fights already won.
- generated-enemies-bench (2026-11-07): done at the cap; 24-mechanic table, +1.28 (0.38) HP
  over 21, the cost follows the punish-an-action trigger; adapted column to gen-adapted-column.
- session-free-reads (2026-11-08): done; a family runs from one queueing
  session to its table; the ledger committed.
- gen-adapted-column (2026-11-08): done; about 100 games adapt to each of four generated mechanics, either teacher; 33 too few.
- strength-by-hits-left (2026-11-08): fail; the price cut Nob's cost 71-93% but
  no scale kept AttackLoss-Strength within 1.5 HP on every parent.
- pack-adapt-pipeline (2026-11-08): go; one command from pack to net, Nob cut
  0.75-0.87, but the shipped net passes the guard at its bar (Lagavulin leak).
- pack-retention (2026-11-08): fail; the weight anchor fixes the parents but trades the TurnEnd-Frail x Lagavulin leak against the Nob cut (a003 +2.76 HP at seed 2; a03 keeps +7.59 of the cut); the heuristic teacher lost the cut.
- all-content-net (2026-11-08): closed at the cap; two of three seeds pass the boss bar, mostly held-out cards (Demon Form, Metallicize); Guardian +0.035 outside Demon Form, headline not read; the go left unfinished (decisions "After all-content-net's close"), the recipe returns as `learn-memory`'s pack net.
- few-game-recipe (2026-11-08): go; 33-game bursts at replay share 0.8 cut AttackLoss-Weak 0.79 (net teacher) and 0.52 (heuristic, parent guard missed by 0.07); lr/3 lost; games-to-adapt at share 0.5 overstated.
- pack-pick-split (2026-11-08): fail; barred from the pack cards both players lose 0.12-0.14 clears more than with the pack: the pack drop is dilution, the chooser's pack picks help.
- act1-content (2026-11-09): closed at the cap; monsters kind done (7/7 from a pack, re-rank passed: no zero-shot gap for net or search); cards 27 written, 13 blocked (C3, C5-C14).
- finish-faster-tiebreak (2026-11-09): fail; exact-tie breaks cut no search nodes (-0.003%, turns -2.6%, HP identical over 330 replayed fights).
- queue-throughput (2026-11-09): fail; backfill would have recovered 0.0-1.1 of 19.8 idle-pending hours (no small jobs waited; oversized mem_gb and 14-thread timing jobs held them); decisive-job lane wakes landed.
- share-curve (2026-11-09): go; games to adapt 33 at replay share 0.9 on both mechanics (11 at the edge), parents spared, retention held.
- learn-memory (2026-11-09): go; a 40k-game from-scratch learn peaks at 1.01 GB commit (bar 3.5): pool streamed, solve step reads only its games; same pool bytes.
- random-world-bench (2026-11-09): additive; the net's cost beyond the heuristic for k generated enemy mechanics on the elites stays at most the sum of its singles at k 2-8 (one turn deep); raw difficulty compounds for both players.
- shown-card-numbers (2026-11-10): fail; zero-shot shown numbers and exhaust hidden level on the cell gauntlet (within 0.35 HP); Weak bench rows cut partly, not halved, so recurring-debuff-leaf (24) opens whole.
- recurring-debuff-leaf (2026-11-10): fail; @pd1 cut the Weak rows' HP cost by a fifth (0.19/0.23 at k 4), not half; helps Gremlin Nob, hurts Three Sentries (per-monster over-count).
- pack-net-scratch (2026-11-10): go; three from-scratch pack nets +3.33 HP pooled on the pack headline one turn deep, official cells +1.58 HP; its no-pack twin carries the gain (the recipe, `measurement/pack-net-twin@one-turn`).
- fickle-enemy (2026-11-10): fail; no opening costs the net 1.0 HP per elite fight beyond the control (Skill +0.70, Attack +0.32, Power +0.16); a mild enemy, about one to two Strength.
- player-growth-exposure (2026-11-10): fail at step 1; exposure inside a burst does not teach later ticks.
- from-scratch-later-ticks (2026-11-11): go, then count; a 5000-game-per-group burst on the 10-29 net learns Demon Form's later ticks (+2.69 HP), no fresh start needed.
- counterfactual-state-price (2026-11-11): fail at step 1; greedy-window prices miss every worth (block absorbs the difference; the remaining-rounds scale overprices growth 10-25 times).
- luck-corrected-labels (2026-11-11): fail; the 10-29 net's luck terms add noise (read-sd ratio 1.41) and remove 1% of the label luck on Demon Form decks.
- generated-pack-scratch (2026-11-11): go; a from-scratch net with 18 generated enemy mechanics in its pool cuts the zero-shot cost on 6 unseen pairings by 0.76 over three seeds, official cells and pack headline level or up.
- card-later-ticks-burst (2026-11-11): fail; 5000-game card bursts close neither variant's @tsl1 cost, the same as 400 games: dose is not the lever.
- mechanic-count-curve (2026-11-12): capped before its read; read after by the navigator: go on one seed, the 6-mechanic pack cuts the held-out pairs 0.88 (0.02), above the 18-arm's 0.81: atoms carry the transfer, not the count (`measurement/mechanic-count@six-arm`).
- genpack-product-depth (2026-11-12): between; two turns deep the generated-pack recipe cuts the product's held-out cost by 0.60 (0.20), 0.27 without AttackLoss-Weak, on a cost the second turn already halved.
- wider-generators (2026-11-13): go on one seed; a from-scratch net on the 100-mechanic wide pack cuts unseen pairings 0.84 (0.09), a whole held-out trigger 0.51 and effect 0.95, official cells and pack headline within the bars (-0.25, -0.80 HP).
- genpack-burst-base (2026-11-13): go at 11 games on one base seed each; the generated-pack base cuts 0.60 of its pooled cost, pack-net-scratch 0.10, all on the new effect (Artifact); the deck effect level.
- blind-row-kinds (2026-11-15): ended before it started (one lane at a time); reopens with a second slot.
- machine-throughput (2026-11-15): ended before it started (one lane at a time); reopens with a second slot or when learns bottleneck the queue.

## Candidates

**Open questions** (the navigator's search list; outside research starts
from these):
1. What decides a burst's effect on official play? Part of the spread is
   content, not training seed: bursts on official bosses or
   pattern-modified official fights all read positive on the cells (+0.4
   to +2.4 HP, seed twins 0.4 apart), bursts on SharpHide or stat shifts
   level or below, with SharpHide's seed twins 1.7 apart
   (`decision/burst-adapted-column`). Adapted columns keep three burst
   seeds. Such a gain reaches the product as about +1 HP and no clears
   (`decision/crossed-player-lead`), so the question matters for one-turn
   play and for what a pack's net costs official play, not for the
   product. Card bursts cost unchanged play one turn deep: all six
   card-modifier bursts lose 0.4-2.4 HP per elite fight on the parent
   copy and the official card, with the replay share in each
   (`measurement/cards-adapted@stage-a`), where monster bursts were level
   on their parents. Open: why a burst against a power that punishes
   attacking varies so much more by seed than a burst on bosses. Not
   missing rehearsal: copy games in the burst's decks raise the elite
   cost (`measurement/copy-rehearsal@stage-a`); the one difference left
   from the level monster bursts is where the games come from (varied
   setups, not the read's fights), not followed while card bursts repair
   nothing @tsl1.
2. Where does goal 1 hurt next? (Answered 2026-11-09 for several
   novelties at once, `measurement/portfolio-random-world-bench`: k
   generated enemy mechanics in one fight cost the net at most the sum of
   their singles beyond the heuristic, so the per-mechanic benches bound
   random enemy worlds and a per-mechanic repair is the unit; cards,
   bosses and two turns deep not covered.) On both rungs the cost sits where a
   payoff or a threat lies past the search horizon, and content that
   lands inside the turn is free because the search plays it in the
   engine. Cards: of ten unseen cards only Demon Form cost, and on
   generated cards the powers that pay at the owner's turn start; the
   turn-start leaf repairs both with no games (Demon Form decks -4.12 to
   +3.43 HP against the heuristic, beside +3.67 and +5.45 on the other
   strata; `cause/unseen-cards-half-edge`), so one turn deep no unseen
   official card costs at 2 se. What is left on cards: two variants'
   small @tsl1 costs (inflame-turn1 -0.018, metal-c2-a5 -0.021 wins;
   pooled over six power pairs -0.006 (0.005),
   `measurement/mutated-cards@stage-a`), which no burst closes at 400 or
   5000 games per group (`measurement/card-later-ticks@5k`: the dose
   teaches the value one turn deep, +0.075 of inflame's boss cost, not
   what the turn-start leaf player still loses), and the leaf routes
   failed (`projected-leaf`, `counterfactual-state-price`); not followed
   (Checked and not proposed, *card-two-turn-cost*). Monsters: powers that punish an
   action and growth (`cause/novelty-is-horizon`); growth (Ritual 2) is
   the one cost nothing has repaired (`race-price`). The generated
   enemies bench's 24-mechanic table (`measurement/gen-enemies@table24`)
   agrees on the family and adds where: the cost follows the trigger that
   punishes the player's own action (attack HP loss +2.98, card played
   +1.62, the monster's turn start or end +0.4 to +0.5; mean +1.28 (0.38)
   HP per elite fight over 21 mechanics), the turn-trigger damage
   mechanics cost nothing against their control, generated growth
   (TurnStart-Strength) only +0.48 (0.12), and most costs sit on one parent
   (AttackLoss-Damage x Gremlin Nob +12.80, the net dying 1,077 times of
   3,664 against the heuristic's 204). Two exceptions run across parents:
   AttackLoss-Weak (+6 on both parents it reads on) and Weak put back each
   monster turn (TurnStart-Weak +2.21, TurnEnd-Weak +2.55, on all three
   parents), where the net learned Weak from sources that let it decay
   (`recurring-debuff-leaf`). Answered 2026-11-08: the Nob cost is the
   leaf's HP price feeding Enrage (`@esp0.04` removes it, +13.29 to -0.06,
   and costs +13 to +22 HP on AttackLoss-Strength), and a 399-game SharpHide
   burst repairs the family on pack enemies across triggers (Nob +13.29 to
   about +2, OppCard-PlainDamage x Sentries +5.39 to about +0.5) but loses
   the net's edge on OppCard-Vulnerable (wins 0.84 to 0.67-0.71;
   `measurement/family-transfer@gen-b1`). Answered 2026-11-08: a burst on one
   generated mechanic loses that one edge in general (a 99-game
   AttackLoss-Weak burst too: Sentries wins 0.765 to 0.58-0.63, everything
   else better; `measurement/bench-retention@gen-b1`), so a pack's net
   reads retention on the whole bench per parent. Answered 2026-11-08: a
   pack's own games in one joint burst keep it (Sentries wins 0.787 against
   0.765) and open a smaller leak on Lagavulin (parent +1.67 HP, TurnEnd-Frail
   +3.25; `measurement/pack-joint-burst@gen-b1`). Open: whether more own
   games or the parents in the burst close it (`pack-adapt-pipeline` step 2). Open: whose games
   teach a recurring power fastest (`yardstick-cards` step 2, plain
   leaf); open question 10; mechanics the
   engine cannot yet express (`act1-content`'s inventory counts them on
   real content); and a mechanic built from an atom the net never read,
   invisible to it and to a burst that keeps the parent's vocabulary
   (`how/burst-inputs`; next-move pattern rows taught nothing in 400-1600
   games, `measurement/portfolio-pattern-rows-burst`).
   Real content answered part of it (`measurement/act1-cards@zero-shot`):
   of the 22 Act 1 pack cards, 19 are level one turn deep with `@tsl1`,
   including the six new-atom cards and the two built on triggers the net
   cannot read, so blindness to an atom costs nothing where its effect
   lands inside the turn. Three in-turn exhaust skills cost (Disarm,
   Impervious, Intimidate), whose value sits in a number left in the leaf
   state, not in damage or cards played: open, why (`leaf-blind-numbers`:
   a Strength below zero, which training never shows, and leftover block,
   which the leaf shows only when a monster's next move is random).
   Answered 2026-11-13 (`cause/roundend-blind`): every RoundEnd row costs
   about 2 HP beyond parent on every recipe because the net cannot see the
   power: the encoder writes `RoundEnd` hooks only as the opt-in
   `countdown` kind, which no net turns on; untrained turn-trigger damage
   costs pns1 the same +2.8, and training removes it there (candidate 71,
   65's step 0). Covered atoms otherwise transfer
   (`measurement/mechanic-count@six-arm`). Open: which other custom
   content the default row kinds hide (72).
3. What does the second turn of search find at Hexaghost (+0.083 wins on
   the same decks, most at 40-59 HP; `measurement/depth-by-boss@replay`)
   that outcome labels do not teach (`measurement/unseen-boss-burst@replay`),
   and does a third turn find more (`hexaghost-headroom`)? The code read
   is done (`how/burst-inputs`): Divider's damage is in the inputs; Burn's
   cost is not in the product net's (the boss bursts had it and gained
   nothing); the place in the move cycle is in no net's inputs except
   through the turn count. Rows showing the next move taught nothing
   (Hexaghost +0.004 (0.002), `measurement/portfolio-pattern-rows-burst`);
   open: rows unrolling two or more moves, the cycle position as a
   column, or labels from a deeper teacher.
4. What do published few-shot or continual adaptation methods for
   game-playing nets rely on (meta-learning, rehearsal, adapters), and do
   their preconditions hold here: a small value net, CPU-only training in
   minutes, retention read on official content? A prior-art scan (`prior-art-card-ai`).
5. How do other StS bots (sts_lightspeed's agents, sts-ironclad-agent)
   behave on content they were not written for, do any read the draw
   order, and how do they fare against Hexaghost? Engineering scan, same
   run.
6. (Goal 2) Two-turn search holds on the held-out book at about two
   thirds of its screening-book size (`measurement/headline@confirm-book`).
   Whether the settings chosen on 0-499 shrink the same way (@hpe over
   @hpb, line-step over plain two turns) is read only if a goal-2 read
   needs it: each was adopted as level, so the expected difference is
   about zero against a detectable 0.07 clears.
7. (Goal 2) What is goal 2's next question worth CPU? Depth, training
   recipes, boss bursts and run-level choices are closed or parked. At a
   fixed entry HP the product's decks differ by 0.2-0.3 in boss win rate on
   the Guardian and Hexaghost, two to three times what the second turn of
   search adds (`measurement/depth-by-boss@replay`), and the deck is the
   chooser's, which waits for Act 1's cards: goal 2's next gain most
   likely comes through `act1-content` or the chooser (`value-chooser`),
   not through the fighter. `crossed-player` agrees: the best burst net
   fights +2.5 HP better one turn deep and two turns deep keeps +1 HP and
   no clears, because depth already wins the boss fights the leaf learned
   (`cause/leaf-gain-third`); clears follow boss wins
   (`cause/boss-deaths`). The one fighter route left is a leaf that sees
   what two turns do not; its pattern-rows probe failed
   (`pattern-rows-burst`), and a leaf that learned powers' later ticks
   from games is one (`measurement/pack-net-scratch@two-turn`, three
   seeds: +4.57 (1.19) HP and +0.097 (0.030) clears two turns deep on the
   31-card pack, at the bosses, 1.35 (0.50)x its one-turn gain; two turns
   play only Demon Form's first tick, `cause/unseen-cards-half-edge`). Its
   product use waits for the widened pool; on the curated ruler the twin
   fighter two turns deep on the product's decks gains +1.41 (0.45) HP and
   +0.014 (0.015) clears on 500 sequences, 70% of it on the 39 Demon Form
   decks, +0.98 (0.47) and level clears on the rest
   (`measurement/pack-net-twin@two-turn`): the second net after the
   crossed-player burst net to land at about +1 HP and no clears two turns
   deep (`decision/crossed-player-lead`). The chooser side has one measured
   error with a sign, and it belongs to the leaf repair: with the turn-start
   leaf Demon Form picks rise 0.17 to 0.49 and the extra picks cost -0.115
   (0.066) clears, but the all-content twins, which learned the card from
   games, pick it 0.62-0.69 and gain where only they took it (clears +0.09
   to +0.12; `cause/chooser-horizon`, `measurement/pack-net-twin@one-turn`).
   The horizon's blind spot on the elites stays unpriced; `value-chooser-path`
   (45) holds every elite ahead and waits for Act 1's cards; open question
   11 counts the cards it would act on.
   And one measured lead: picking by the net's static values beats the
   trial fights by 4 to 5 HP and 0.06 clears on train-card sequences one
   turn deep and loses 4 HP where offers hold unseen cards
   (`decision/value-chooser-use`), two to three times any fighter lead on
   file; it waits for Act 1's cards. The big-picture review's first
   question.
8. (Answered in part 2026-11-09: since 11-06 a runnable job was pending in
   19.8 idle hours; no small job waited
   behind a big one, so the hours were job size (memory reserved above
   real peaks, 14-thread speed checks), not ordering;
   `measurement/queue-backfill-replay`.) What is the machine for, now
   that comparisons play one turn deep? A
   lane's reads cost minutes, so lanes wait on code and specs
   (`cause/one-turn-frees-cpu`). What binds the CPU is memory: on 2026-11-06 no
   job ran for 14 hours because every pending job reserved more than the
   memory then free (a burst 4.5-5 GB, the heavy tests 9.5
   GB), and a lane whose jobs cannot start gets no lane worker, because a
   pending job counts as busy (`cause/memory-holds-bursts`). A training
   by `learn.py` on 5,000 games peaks at 1.2-1.6 GB against a burst's
   2.8-7.4 GB, so the burst's peak is not training itself (`yardstick-cards`
   step 2a). Open: what fills fourteen threads once bursts fit: training
   on generated content at scale (the enemies bench's coverage curve),
   the enemies bench (`generated-enemies-bench`), or reads on Act 1's new
   content as it lands (`act1-cards-zero-shot`). The cheapest filler stays
   reading existing files again by a new split (by card, by trigger, by
   the pack's keys: the Demon Form finding and the same-row finding cost
   no CPU).
9. What does a burst net cost on unchanged elites two turns deep? It
   varies by net: two SharpHide burst seeds lose 0.60 and 1.67 HP per
   fight (`measurement/adapted-two@elites`), the SharpHide-then-stage-B
   net gains 1.39 HP per run at the headline's elites
   (`measurement/crossed-player@two-turn`). So it is not a property of
   fine-tuning (a shifted value scale would cost every burst net), and
   the one-turn ruler cannot see it: a net headed for the product owes
   its own two-turn retention read (`cause/leaf-gain-third`). Read again
   when a pack's net is to play in the product (runtime-registry stage 4).
10. (Answered 2026-11-07, `yardstick-cards` step 2b: no. Nets that
   learned the trigger and the effect on different cards gain nothing on
   the pair (parts -0.13 (0.66) HP on Demon Form decks, level with
   neither), and what any burst taught on the pair was its first tick
   (`measurement/demon-form-games@tsl1`). So the enemies bench's coverage
   curve counts pairs, not atoms; `projected-leaf` takes the later
   ticks.)
11. Which of Act 1's missing Ironclad cards pay over later turns, and do
   they cost the one-turn net as Demon Form does? The inventory
   (`docs/research/act1-inventory.md`, the navigator's count from its
   lists) names 40 missing cards: 16 are written as pack data
   (`measurement/act1-cards@files`), 24 wait for building blocks. Eight
   of the 40 are powers whose payoff comes in later turns: Berserk
   (written; energy at each turn start) and seven blocked ones
   (Corruption, Dark Embrace, Feel No Pain, Evolve, Fire Breathing,
   Barricade, Juggernaut). Only Berserk pays at the turn start; the
   others pay on an event inside a later turn (a card exhausted or
   drawn, block gained or kept), which the search plays once the power
   is up, so their cost is the turn spent playing them, not a tick the
   leaf misses. Berserk does not cost the net, on either leaf: the net
   leads the heuristic by more with it (+0.070 (0.032) wins), both lose
   wins with it, and `@tsl1` changes nothing on it
   (`measurement/act1-cards@zero-shot`). Open: the seven as their blocks
   land (Dark Embrace and Feel No Pain landed with C2), and which of them
   the chooser's horizon overpicks once the fighter plays them (question
   7, `cause/chooser-horizon`).

12. (Goal 2) Is the 14-19 HP lost per elite forced by the deck, or a
   blind spot every player shares? Three steps of player strength moved
   it by about 2 HP each; only a bound (`ceiling-player`) or a per-turn
   trace can tell (review 2026-11-06).
13. Does a gain one turn deep predict the gain two turns deep, net by
   net? Small leaf gains reach the product at 0.2-0.46 of their size
   (`cause/leaf-gain-third`), while the base net's edge over the
   heuristic leaf grows with depth (+5.4 to +9.3 HP). The ledger's
   transfer table (`experiment-ledger`) answers it from pairs on disk;
   the ledger found no recipe with a two-turn cell read yet. Answered in
   part 2026-11-10 by kind of gain: a from-scratch net that learned
   powers' later ticks carried 1.35 (0.50)x on the 31-card pack (three
   seeds, `measurement/pack-net-scratch@two-turn`): by kind of content,
   in-horizon threats a third, past-horizon payoffs whole
   (`cause/leaf-gain-third`). A third kind may exist: the all-content
   twin gains +1.38 (0.76) more two turns deep than one outside Demon
   Form on the same decks (twin-depth-paired, 1.8 se, a lead: the second
   turn repairs its elite deaths); and content paying partly inside the
   second turn splits by part (Demon Form 0.56x, as predicted).
14. (Goal 2) How much of the Hexaghost and Guardian loss is the setting?
   The headline plays with no potions and a 30% heal before the boss, so
   the "runs are lost at the boss" picture (`cause/boss-deaths`) may move
   once relics and potions are in (`act1-content` step 4); re-read the
   death split on the first setting with them, before any boss work.
15. (Goal 1) Does `codec.rs` still refuse states holding pack content
   after registry stages 2-4? If so, `exact-referee` needs that change
   before the solver can be goal 1's absolute ruler (review 2026-11-09).
16. (Goal 1; owner discussion 2026-11-09) Can the net learn what a
   source is worth (a power, a card left in a pile, a point of Strength)
   when its benefit lands turns later? Two cases on record: Demon Form's
   later ticks (`cause/unseen-cards-half-edge`,
   `measurement/portfolio-projected-leaf`) and the prices of cards in the
   piles (`measurement/pile-prices@pairs`: held-out correlation 0.20 with
   the played-out change). Showing the effect repairs what lands inside
   the search (`@tsl1`) and gives small zero-shot gains (candidate 44,
   `shown-card-numbers`); teaching it has not: final-score labels are flat
   (`cause/teacher-equals-student`) and interventional pair labels (the
   same position with and without the source, played out over the same
   futures) plateau at about 0.3 under every fit tried
   (`measurement/pair-fit@recipe`), and bursts of up to 1.6k games learn
   Demon Form's first tick only, at any exposure share up to 52%
   (`measurement/portfolio-player-growth-exposure`). One recipe did teach
   it: 40k from-scratch games with the power in the pool (+3.30 (0.95) HP
   @tsl1, `measurement/pack-net-twin@one-turn`); what in that recipe did
   it was the dose: a 5000-game-per-group burst on the 10-29 net learns it
   too (+2.69 (0.91) HP, `measurement/later-ticks-count@burst5k`; 1.6k
   taught the first tick), so the games number for a later-ticks power is
   1.6k-5k per group; on the card yardstick's two variants the same dose
   closes neither @tsl1 cost (`measurement/card-later-ticks@5k`). Answered 2026-11-11 for powers no game
   held: what such nets learned carries to unseen generated recurring
   powers through the effect inputs (+0.03 to +0.09 wins over ten nets,
   `measurement/gen-powers@later-ticks`). Open: whether an input change
   (shown numbers, a card summary that sees the player's state) lifts what
   pairs can teach, and whether a stronger teacher's play-outs do.
   `docs/research/pile-prices-2026-11-09.md`.
17. (Goal 1) Does breadth of training content buy zero-shot transfer to
   novel mechanics? Every goal-1 repair so far is per mechanic, after the
   fact (a burst per pack, a leaf per trigger); a base net that had seen a
   space of mechanics might need no games on a new one from a family it
   has seen. Evidence so far: within the punish-an-action family a burst
   on one mechanic cuts others across triggers
   (`measurement/family-transfer@gen-b1`); on cards a trigger and an
   effect learned apart did not compose (`yardstick-cards` 2b); a
   from-scratch learn on the Act 1 pack lost nothing on official cells
   (seed 1 +1.61 HP). On the generated bench the pack net lost
   zero-shot play on five of seven costly rows
   (`measurement/pack-net-gen-bench@seed1`): official breadth did not
   carry, and 0779-0780 read whether the recipe or the pack's few powers
   did it. On cards it did: an all-content net with no pack plays the 31
   pack cards zero-shot about as well as the pack net (+0.38 (0.73) HP
   short, `measurement/pack-net-twin@one-turn`), so new cards need no
   games one turn deep and new mechanics are the question;
   `generated-pack-scratch` (47, open) is the direct test. Outside
   research (checked 2026-11-10, entry 47): Procgen needs hundreds to
   thousands of levels; factored card representations carry to unseen
   cards in Hearthstone and Magic agents. On enemy mechanics the answer
   is yes, and past the pool's atoms: the 18-mechanic generated-pack net
   cuts 76 mechanics built on triggers and effects no enemy power in its
   pool had by 0.60-0.81 against pack-net-scratch (job 0898), except
   effects that act through the player's deck (Wound -0.11, Dazed
   0.31-0.56) and Artifact. Open: what the pool teaches, reading enemy
   power rows through shared columns, or pricing the fight states powers
   lead to (64; `wider-generators`' step 2b row ablation decides).

18. (Both goals' rulers; review 2026-11-10) Does the end-HP statistic
   reward HP that is worth nothing? It counts HP left after the Act 1
   boss, which the real game heals at the act transition below Ascension
   5 (to be checked against the wiki and sts_lightspeed,
   `decision/parity-source`); that part is 30-55% of small end-HP edges.
   If the heal holds, a read's score is better taken at boss entry or as
   clears plus HP at the boss; no read changes until it is checked.

Ranked by the navigator under `docs/direction.md`, which outranks every
review; within a goal the order follows the newest
`docs/research/big-picture-*.md` (2026-11-11). Comparisons play one turn
deep unless the question is about search depth
(`decision/one-turn-comparisons`). Run-level decision work waits for the
content it chooses between (direction "Avoid"). Rank = rating x what it
moves x cost; one turn deep a candidate's CPU-hours hardly rank it, its
code does (`cause/one-turn-frees-cpu`).

Each candidate states its predicted effect beside what its read can
detect with the seed spread counted (`measurement/seed-sd@gauntlet`: a
single-seed pair's se is about 1.1 HP), the unit its claim generalises
over (sequences, seeds or content items; for goal 1 the mechanic), and
the error it repairs. A lead of 2-3 se from one seed, one book or one
content item opens nothing; it gets a replication on fresh sequences or
seeds.

Open lanes (2026-11-13, after the review `docs/research/big-picture-2026-11-12.md`,
which outranks this order, and the navigator run after
genpack-burst-base's go):
`wide-recipe-confirm` (project, 65 with 71 as step 0; seeds 101 and 201
first), `machine-throughput` (project, 66; code first, one confirming
learn), `blind-row-kinds` (exploration, 72; code first) and
`act1-content` (owner-led, `decision/act1-owner-led`). The 6-arm read
(`measurement/mechanic-count@six-arm`) says covering a mechanic's atoms
is what transfers; what is left zero-shot on single-hook pairings of
covered atoms is 0.1-0.6 HP. genpack-burst-base (`measurement/gbb@g11`)
adds that a pool-trained base binds a trained column on a new pairing in
11 games where the pool-less recipe gets worse, and the wide base
already pays nothing there (+0.29 HP on GE-OppCard-Artifact). So goal
1's open cost is atoms no content trained (73), atoms the net can't see
(72), several hooks in one power (68), held-out whole triggers and
product depth (`measurement/genpack-transfer@two-turn`). Ranking, goal 1
first (development weight 0.8), with the owner's 75 ahead of it while
its reads run (no lane, no code). 75 is done but for (c)'s code flip and
(d), which rides on the next from-scratch net. 77 `product-level-flags`
is done: read 2026-11-13, level: the product gains `@tsl1@lcb1` and the
`@hpe0.01@lcb1` chooser (decisions "Product read 0986").
- **One lane at a time** (`decision/one-lane`, 2026-11-14): every
   lane session goes to `lane/final-round` (78 below) until the final
   round is queued and read. The ranking below is for the next slot after
   it; no candidate holds a ready charter meanwhile, so a close opens
   nothing. After the round, the first slot goes to 68 (its charter is
   written and held), the exploration slot to 73; 66 (throughput) and 72
   (row kinds) return beside them when two lanes run again.
- **78 `final-run-inputs`** (open as `lane/final-round` (2026-11-14)):
   the owner's final training round at A20, with 82 and 85 probed as its
   step 2 (decisions "The stall probes become final-round's step 2").
0. **76 `hpe-leaf-cap`** (likely one turn deep, even for the product;
   a few lines of code, about 10 cpu-h; probe sheet, the first code
   session on main takes it with `tb1-default-flip`): the product's HP
   price misprices running fights near full HP; the cheapest goal-2
   product lever in the record.
1. **68 `multi-hook-zero-shot`** (ready charter, the next free project
   slot, once 65's seed-101 grid read is recorded; even, about 4 thread-h
   of reads and half a day of code): the next width after single hooks.
2. **73 `fresh-column-burst`** (ready charter, the next free exploration
   slot; a long shot at 11 games, even at 33; about 4 thread-h and half
   a day of code): the few-game case real custom content brings, an atom
   whose input column nothing trained.
3. **74 `gbb-second-seed`** (likely, about 3 cpu-h, no code): turns
   the 11-game lead into goal 1's quote; a slot with idle CPU and nothing
   queueable takes it.
4. **70 `wide-full-triggers`** (a long shot since 0939-0941: Thorns 2
   moves about 1.9 HP with the training seed alone); out of 65's charter.
5. **62 / 64** (long shots, decided by `column-zeroing` on the
   probe sheet), **69** (no CPU; goal 2's
   ruler, the fallback for a slot with nothing queueable), **55** (goal
   2, cheap), **41** (character as data).
Goal 2 (CPU weight 0.4): the product stays the 10-29 net
(`decision/crossed-player-lead`), now `@hpe0.01@tsl1@lcb1` with the
`@hpe0.01@lcb1` chooser (`product/net`), quoted as 0.78-0.81 clears
(`decision/headline-quote`); run-level decision work waits for Act 1's
content, so goal 2's share mostly runs ruler checks (69, 55). The
navigator wakes for results that could change the ranking or a lane.

**Probe sheet** (reads that need no code and under about 5 thread-hours:
no lane, charter or wake of their own; the navigator queues them in lane
`main` with the read rule in the job's note and reads them at its next
run):
- **hpe-leaf-fix** (backlog 76; waits for code, a few lines and a test):
  a suffix that keeps `@hpe`'s heal and cap on won states only and prices
  unfinished leaves by linear HP; then the 10-29 net `@hpe0.01` with it,
  one turn deep with the plain leaf, headline n 500, `--against` the
  plain `@hpb0.01` file `results/gauntlet/net1029-hpb0.01-starter-simboss.json`
  (`--vary price`; not the `@tsl1` controls, which would confound the
  leaf), paired also against 0970's
  `results/gauntlet/net1029-hpe0.01-starter-simboss.json`; read rule in
  76's entry. About 2.4 thread-h.
- **tb1-default-flip** (waits for code, about a line; `decision/tb1-default`):
  the search's exact-tie break on by default, `@tb0` to turn it off; check:
  rerun 0680/0681's replay (sequences 0-29 of the headline control, every
  floor) with end HP and wins identical in all 330 fights. Any code session
  on main may take it; no read follows.
- **column-zeroing** (waits for code: an evaluator option that zeroes
  named feature columns of hook rows; Source: `wider-generators`' step 2b,
  moved here 2026-11-13, decisions "After the filler hold"; decides 62 and
  64): the seed-1 generated-pack net and the wide s1 net @tsl1 on the 6
  old held-out rows, the trigger column zeroed, then the effect column,
  against their unablated files (`gen-gp1-tsl1-all24.json`,
  `gen-wp1-tsl1-all24.json`), and the whole generated power row zeroed on
  the same rows plus GE-Attacked-DexDown, GE-OppAttack-DexDown,
  GE-Attacked-Vulnerable, GE-TurnStart-StrDown, read against pns1's
  unablated files. Read: under 1 HP lost to zeroing a column retires 62
  (names carry little); over 2 HP opens a design. About 5 thread-h.
- Read 2026-11-12, job `0934`, **wide-gen-powers** (descriptive since 67
  retired; `docs/research/genpack-yardstick.md`, "The wide net on the
  generated-power bench"): the wide net is +0.069 (0.023) wins over the
  heuristic on the 52 non-recurring generated cells (10-29 net +0.037)
  and the first net with no recurring-power gap (generated minus original
  -0.022 against -0.079): enemy breadth costs player-power play nothing.
- Read 2026-11-12, jobs `0939`-`0941`, **genpack18-yardstick**
  (`measurement/genpack-yardstick@18-seeds`, `docs/research/genpack-yardstick.md`,
  "The 18-mechanic nets on the yardstick"): **between**. Pooled novelty
  cost +0.96 / +2.27 / +2.01 HP over seeds 1 / 101 / 201 against pns1's
  +4.03 and the wide s1's +0.92: the 18-mechanic pool gives most of the
  cut, seed 1 is good for both recipes, thorns2 spreads 2.45-6.28 over the
  seeds (70 falls to a long shot and leaves 65), and Ritual 2 is repaired
  by every 40k from-scratch net (`cause/novelty-is-horizon` re-set). The
  probe as queued (lane main, pin c5bf088, the
  same snapshot as 0931-0933 so the heuristic's games are identical),
  **genpack18-yardstick** (Source: navigator ideas run 2026-11-12, from
  `measurement/genpack-yardstick@18-seeds`): the same yardstick rows for
  the 18-mechanic generated-pack nets seeds 1, 101 and 201. Mechanism:
  the 18-mechanic pool trains OppCard-PlainDamage (damage back on any
  card), the nearest grid pair to Sharp Hide, so it may already carry
  most of the wide net's yardstick cut. Trade-off: the 18-mechanic nets
  gain if the cut needs only the old triggers; the wide grid's new
  triggers (OppAttack, OppSkill, AttackHit) gain if they carry it; each
  can win. Read against `yard-pns1-tsl1.json` (seed 1; no other pns seed
  has these rows): replicated if all three seeds' pooled cost over
  sharp2, thorns2, ritual2, weakhit1 is at most half pns1's 4.03 at 2 se
  (the generated pool moves the yardstick over three seeds; 65's
  yardstick measure becomes a check, not the evidence); the wide grid
  carries it if they pool within 0.5 HP of pns1's (65's seeds are the
  only replication); between, the seed spread is the number. About 2.5
  thread-h.
- Read 2026-11-12, jobs `0931`-`0933`, **genpack-yardstick**
  (`measurement/genpack-yardstick@18-seeds`, `docs/research/genpack-yardstick.md`):
  **go**. The wide net's pooled novelty cost over sharp2, thorns2,
  ritual2 and weakhit1 is +0.92 (0.19) HP against pns1's +4.03 (0.28)
  and the 10-29 net's +3.41 (0.25) (wins +0.003 against +0.058); Sharp
  Hide is repaired on every elite, Thorns is left at the 10-29 net's
  level (+4.20), on the trigger the wide pack held out (70 follows from
  it); the wide net's parent edge is 0.63 (0.26) HP below pns1's. One
  seed: 65 carries the yardstick as a measure. The probe as queued:
  (Source: navigator ideas run 2026-11-12, from
  `wider-generators`' step-3 files read early by the navigator (0916:
  the wide net cuts the new held-out pairs to +0.25 (0.15) HP beyond
  parent, cut 0.94 (0.04) against pack-net-scratch s1; the whole held-out
  trigger Attacked to +0.52, cut 0.91; 0917: the old 6 held-out pairs to
  +0.10 (0.15)) and the gap that no generated-pack net has been read on
  the owner's yardstick (`decision/goal1-yardstick`: boon + bane pairs on
  official parents, `measurement/mutated-monsters@stage-a`); goal 1's
  standing number): the stage A singles and pairs on official elites
  (sharp2, thorns2, ritual2, weakhit1, metal3, their boon + bane pairs,
  str2 and hp1.25 as the plain controls), 675 elite starts x 2 seeds
  @tsl1 one turn deep, for the wide net (widepack40k s1, 0931), pack-net-
  scratch s1 (the same recipe without a generated pool, 0932) and the
  10-29 net (0933). Mechanism: the yardstick's costs sit on powers that
  punish an action and on growth (`cause/novelty-is-horizon`), the family
  the wide grid trains (OppAttack, OppSkill, AttackLoss, Attacked x
  Strength, Damage, debuffs); Sharp Hide, Thorns, Enrage and WeakOnHit
  themselves were left out of the grid as official pairs, so each is an
  unseen pairing to the wide net. Trade-off: the wide net gains if the
  generated pool taught the family; pns1 gains if the pool cost official
  strength (on cells it read level or up, so mostly not); each can win.
  Read: per modifier novelty cost `(net - heur)(mod) - (net - heur)(parent)`
  paired by start over the three files. Go if the wide net's pooled cost
  over sharp2, thorns2, ritual2, weakhit1 is at most half pns1's at 2 se
  (the generator moves goal 1's standing number with no games on it: the
  yardstick becomes a measure of 65, `wide-recipe-confirm`); stop if within 0.5 HP of pns1's (the grid does not reach
  official mechanics; 53's next step asks why). About 3.5 thread-h.
- Read 2026-11-11, jobs `0890`, `0891` (control re-run `0893`),
  **gen-powers-later-ticks** and **genpack-gen-powers**
  (`measurement/gen-powers@later-ticks`): go on both rules. Every one of
  ten nets that learned a power's later ticks from games (from-scratch
  twins 5k-40k, the three 5k bursts, the three generated-pack nets) gains
  +0.03 to +0.09 wins on generated recurring powers no game held (families
  +0.049 to +0.078), and none on the other generated powers; that closes
  the 10-29 net's -0.05 to -0.07 gap to the heuristic there. 56 answered
  (Checked and not proposed); the generated-pack recipe is goal 1's one
  base net for unseen enemy pairings and unseen recurring player powers
  one turn deep, which 60 reads two turns deep.
- Read 2026-11-11, jobs `0895` and `0901`-`0903`, **pick book
  1000-2999** (Source: review 2026-11-11, direction 2; both goals' fighter
  reads): the one-turn control unmatched on fresh sequences, recording its
  picks for matched reads (`decision/matched-reads`). Block 1000-1499 ran
  in 39 minutes (estimate 70), clears 0.668 and end HP 21.7, like the
  other books (`yardstick/books`); jobs 0901-0903 ran blocks 1500-2999
  (`results/gauntlet/net1029-hpb0.01-starter-simboss-{1500,2000,2500}.json`).
  No pass or fail.
- Read 2026-11-10, jobs `0793`-`0796`, **twin-tsl1**
  (`measurement/pack-net-twin@one-turn`, its @tsl1 part): go. The twins
  @tsl1 beat the 10-29 net @tsl1 on Demon Form decks by +3.30 (0.95) HP,
  other held-out -0.04, train +0.56: from-scratch games taught Demon Form
  past its first tick. 49 goes to even with the next exploration charter;
  0777-0778 released.
- Read 2026-11-10, jobs `0791`-`0792`, **pns-twin-matched**
  (`measurement/pack-net-twin@one-turn`, its matched part): the twins on
  the control's picks +1.15 (0.57) HP pooled, under the bar; Demon Form
  decks +14.07 and +12.71, the other 457 sequences +0.05 (0.56). The
  twins fight level outside Demon Form, so about 1.5 HP of the own-pick
  shortfall is the one-round recipe's picks (about 1.4 se, a lead):
  47's own-pick pack-headline reads may carry it, its fixed-deck reads
  do not.
- Read 2026-11-10, jobs `0782`-`0783`, **pns-twin-official**
  (`measurement/pack-net-twin@one-turn`, its ruler part): fail, +0.76
  (0.87) HP pooled, clears +0.028; candidate 48 retired. The gain is Demon
  Form (both took it: +19.2 and +15.6 HP; picks 0.62-0.69 against 0.19);
  where no player took it the twins lose -1.50 (1.00) HP, deaths moving
  from the boss to the second elite.
- Read 2026-11-10, jobs `0770`-`0773`, **pns-twin**
  (`measurement/pack-net-twin@one-turn`): the recipe branch. The no-pack
  twin carries 87% of the pack net's pack-headline gain (pack net minus
  twin +0.38 (0.73) HP pooled; seeds -1.14 and +1.91), and the pack costs
  official cells -1.09 (0.39) HP by dilution; twin on cells +2.32 (0.54)
  against the 10-29 net. Effect inputs carry the pack cards zero-shot; the
  gain is from scratch on every official card.
- Read 2026-11-10, jobs `0774`-`0776`, **pns-official**
  (`measurement/pack-net-scratch@three-seeds`, its ruler part): fail, the
  three pack nets one turn deep on the ruler pool to +0.78 (0.89) HP,
  clears +0.011. The gain is Demon Form (+17.7 to +20.2 HP where both
  took it); where no player took it -2.14 (0.97), deaths moving from the
  boss to the second elite, as the twins': the one-round recipe's picks.
  No two-turn official read (decisions "Probe pns-official read").
- Read 2026-11-11, jobs `0842`-`0843`, **genpack-reach (a) stacks**
  (`measurement/genpack-reach@stacks`): composes. On worlds of 4
  generated mechanics the generated-pack net's cost beyond the heuristic
  is +3.16 (0.18) HP at the death cap against pns s1's +6.16 (0.23)
  (paired -3.01 (0.18), ratio 0.51, the rule's line; 0.17-0.22 at looser
  caps); a stack keeps about four fifths of the singles' cut. The k-4
  bench joins 53's step-3 reads.
- Read 2026-11-11, jobs `0844`-`0845`, **genpack-reach (b) bosses**
  (`measurement/genpack-reach@bosses`): go. On the 325 official boss
  fights the held-out pooled novelty cost falls +1.21 (0.26) to +0.23
  (0.26) HP, cut 0.81 (0.19), wins +0.030 (0.009); the base cost is a
  quarter of the elites'. Both reach probes went: bosses stay out of 53's
  pack; 52 on 47's pooled go reads the pooled generated-pack net.
- Queued 2026-11-10, jobs `0842`-`0845`, **genpack-reach** (Source:
  navigator ideas run 2026-11-10, from 47's seed-1 go and its split by
  parent, `docs/research/genpack-host-split-2026-11-10.md`; goal 1): how
  far the generated-pack net's zero-shot cut reaches beyond the bench it
  was read on, with no new training, seed 1's net against pack-net-scratch
  seed 1, both @tsl1 one turn deep. (a) Stacks, 0842-0843: random worlds
  (`random_world.py nd-play`, k 4, 40 worlds, 50 starts x 4 seeds,
  no-death), each net's base file as `--base`; the pack showed one
  mechanic per encounter, so k at once is composition the net never saw.
  Go (composes) if genpack's k-4 cost beyond the heuristic is under half
  of pns s1's at 2 se. (b) Bosses, 0844-0845: the 24 mechanics on the
  official bosses (325 boss fights x 4 seeds), a host kind the pack never
  carried, where fights run past the horizon and deaths sit
  (`cause/boss-deaths`). Go if the held-out pooled boss cost falls by 0.4+
  at 2 se; stop if pns s1's held-out pooled boss cost is under 1 HP. Rated
  **likely** on (a) (the singles' cut is 0.81 held-out and 1.62 on
  training rows, and costs add, `measurement/random-world@nodeath`) and
  **even** on (b) (for: Lagavulin's whole cost went; against: no boss in
  training games carried a mechanic, and boss costs are horizon costs).
  Predicted against `yardstick/read-floors`: (a) a 3+ HP difference at k 4
  against a se of about 0.5-0.7; (b) a 2 HP pooled gain if base costs are
  near the elites' +5, se about 0.5. About 6 thread-h. What each outcome
  changes: two gos make the pooled seeds' net goal 1's base for enemy
  mechanics with bosses and stacks included and 52's product-depth
  question one for that net; a boss fail puts bosses into 53's generated
  pack before its learn.
- Read 2026-11-11, jobs `0855`-`0857` with `0854`, **twin-depth-paired**
  (`measurement/pack-net-twin@two-turn`, its paired part): stop at 1.8 se.
  On the product's decks outside Demon Form the twin is -0.40 (0.62) HP
  one turn deep (seed 101 -0.92) and +0.98 (0.47) two: growth +1.38
  (0.76), a lead, with the second turn repairing the twin's second-elite
  deaths (one turn 33 and 41 against 26; two turns 8 against 13).
  One-turn screens stand. The Demon Form decks keep 0.56 of their one-turn
  gain, the mix `cause/leaf-gain-third` predicts (first tick at a third,
  later ticks whole: about +6.0 against +6.46 measured); the cause gains
  that case. Decisions "twin-depth-paired read: stop".
- Read 2026-11-11, jobs `0846` and `0854`, **twin-two-turn-matched**
  (`measurement/pack-net-twin@two-turn`): between at 500, no second seed.
  The twin seed 1 two turns deep on the product's decks, 0-499: +1.41
  (0.45) HP (protocol pass at n 500), clears +0.014 (0.015), boss deaths
  62 to 54 (paired 28 against 20, z 1.15; go needed 10 fewer). The 39
  Demon Form decks +6.46 (1.41); the other 461 +0.98 (0.47), clears level;
  the twin's second-elite saves (8 deaths against 13) die on the next
  hallway (13 against 6). With the crossed-player burst net, two recipes
  land at about +1 HP and no clears two turns deep:
  `decision/crossed-player-lead` re-set. Decisions "twin-two-turn-matched
  at 500: between; no second seed; the fighter plateau has two nets".
- Read 2026-11-10, jobs `0819`-`0820`, **pns-two-turn-seeds**
  (`measurement/pack-net-scratch@two-turn`): go. Seeds 101 and 201 two
  turns deep +4.42 (1.42) and +4.62 (1.49) HP; pooled with seed 1 +4.57
  (1.19) HP, clears +0.097 (0.030), one turn deep +3.38, ratio 1.35
  (0.50); boss deaths 60 to about 42. `cause/leaf-gain-third` re-set:
  past-horizon content gains reach the product whole.
- Read 2026-11-10, jobs `0777`-`0778`, **pns-two-turn**
  (`measurement/pack-net-scratch@two-turn`): go, a lead. Pack net seed 1
  two turns deep on the 31-card pack +4.67 (1.40) HP, clears +0.080
  (0.033) against the product; +2.80 (1.37) one turn deep on the same
  sequences, ratio 1.67 (0.86), 2.3 se above the leaf rule's prediction.
  At the bosses (boss-floor deaths 60 to 37), not Demon Form alone
  (+3.10 (1.48) where neither took it). The product on this pack: 0.636
  clears against 0.836 curated (`decision/headline-quote`).
- Read 2026-11-10, job `0779`, **pns-gen-attribution, twin**
  (`measurement/pack-net-gen-bench@seed1`, its attribution part): the
  recipe. The no-pack twin loses the OppCard-Vulnerable edge (-0.267 wins)
  and the OppCard damage rows as the pack net does; 47's step 2 keeps the
  recipe and gains step 2b, a round-2 read if seed 1 passes the cut and
  fails the 10-29 bar (decisions "pns-gen-attribution read"). 0780
  (pack net seed 101 on the same rows) cancelled 2026-11-10: its format
  does not serve 47's step 4 and no bar reads it (decisions "After the
  big-picture review of 2026-11-10").
- Read 2026-11-10, job `0762`, **pns1-gen-bench**
  (`measurement/pack-net-gen-bench@seed1`): guard branch. Pack net seed 1
  loses more than the 10-29 net on five of the seven costly rows (+1.6 to
  +3.2 HP per elite fight), turns the OppCard-Vulnerable edge into a loss
  (+11.67 HP, wins -0.304), unchanged elites +0.62 (0.16); only the
  Weak-on-action rows gain. Not a goal-1 base for generated packs; 47
  bars against the 10-29 net too.
- Read 2026-11-10, jobs `0734`-`0738`, **pack-dose-33, second read**
  (`measurement/pack-dose-99s9@gen-b1`): between by its rule, adopted: at 99
  games per mechanic and share 0.9 the Lagavulin leak is gone (-0.16 HP),
  Nob's cut +12.18 of +13.29, the Sentries edge kept; one net of two fails
  the guard on another Lagavulin cell (+2.97 HP), as g99 at share 0.5 did
  by more, so pack chains train g99-sh9 (`decision/burst-share`).
- Read 2026-11-09, jobs `0697`-`0701`, **pack-dose-33**
  (`measurement/pack-dose-33@gen-b1`): between. At 33 games and share 0.9
  the Lagavulin leak is gone (+0.54 (0.33) against g99's +3.01), but Nob's
  cut falls to a third (+4.24 of +13.29) and both nets lose the
  OppCard-Vulnerable x Sentries edge (+7.06 HP, wins -0.213), the guard
  fails on both: the single-mechanic 33-game quote does not carry to
  eight mechanics in one burst.
- Read 2026-11-09, jobs `0702`-`0714`, **card-burst-share**
  (`measurement/card-burst-share@stage-a`): between. At 33 games and share
  0.9 the parent cost per elite fight falls to +0.52 (0.15) HP on
  inflame-turn1 (was +0.76) and -0.33 (0.18) on metal-c2-a5 (was +1.79);
  inflame's plain-leaf win gain is +0.010 (0.004) against the +0.012 bar
  (400 games: +0.024), metal's +0.012; @tsl1 closes nothing. The card
  column keeps both recipes on file; no larger card dose follows (Checked
  and not proposed, *card-burst-dose*).
- Read 2026-11-09, jobs `0715`-`0728`, **share-quote-widen**
  (`measurement/share-quote-widen@sentries`): between. Both damage-trigger
  mechanics pass the cut at 33 games and share 0.9 (OppCard-Damage 0.64,
  OppCard-PlainDamage 0.69 of their costs); OppCard-Damage's parent is
  spared (-0.02 HP), OppCard-PlainDamage's loses +1.68 (0.26) against the
  99-game default's +1.08. The quote widens on the cut to four mechanics,
  two trigger kinds (`decision/burst-share`).
- Read 2026-11-08, job `0566`, **shl-held-out**
  (`measurement/shl0.005@gen-rest`): go. `@shl0.005@tsl1` on the 16 bench
  mechanics outside gen batch 1 breaks no row (worst +0.34 (0.12) HP,
  TurnStart-Frail x Nob), mean -0.41 (0.06) HP per elite fight, Lagavulin
  and Sentries identical (no monster Strength), Nob -1.21 (0.15) with
  AttackLoss-Weak -4.55 and wins up; the trade stays on AttackLoss-Strength
  x Nob (`cause/leaf-price-trades`). Read 2026-11-08, job `0573`,
  **shl-headline** (`measurement/shl0.005@headline`): level, +0.95 (0.64)
  HP, clears +0.012 (0.016), Nob -0.30 (0.40) HP per fight; goal 1's
  candidate leaf, read beside `@tsl1` on new bench tables, nothing for
  goal 2; a price-teacher arm waits for the pack chain after
  `pack-retention` (decisions "After shl-headline").
- Read 2026-11-08, jobs `0549`-`0553`, **pack-joint-burst**
  (`measurement/pack-joint-burst@gen-b1`): between: one burst over gen
  batch 1's eight mechanics keeps the OppCard-Vulnerable x Sentries edge
  (wins 0.787), cuts the Nob cost 0.47 (bar 0.5) and opens a Lagavulin
  leak (TurnEnd-Frail +3.25 HP); a pack's net is one joint burst, and
  `pack-adapt-pipeline`'s first run reads the dose and the parents in the
  burst (decisions "After the pack-joint-burst probe").
- Read 2026-11-08, jobs `0546`-`0547`, **bench-retention**
  (`measurement/bench-retention@gen-b1`): go at the parent: the 99-game
  AttackLoss-Weak bursts lose OppCard-Vulnerable x Sentries (+6.04 HP,
  wins 0.765 to 0.58-0.63) as SharpHide's did, all else plays better; a
  pack's net reads retention on the whole bench per parent
  (`decision/burst-adapted-column`).
- Read 2026-11-08, jobs `0472`-`0474`: **esp-on-gen** (0472,
  `measurement/esp-on-gen@batch1`: `@esp0.04` removes AttackLoss-Damage x
  Nob's cost, +13.29 to -0.06, and costs +13 to +22 HP on
  AttackLoss-Strength on every parent: evidence for
  `strength-by-hits-left`) and **family-transfer** (0473-0474,
  `measurement/family-transfer@gen-b1`: both cut by half, so one burst per
  family covers the punish-an-action damage mechanics; it loses the net's
  OppCard-Vulnerable edge, wins 0.84 to 0.67-0.71).
- Read 2026-11-07, jobs `0456`-`0460`, **copy-rehearsal**
  (`measurement/copy-rehearsal@stage-a`): with the parent copy in the
  burst's decks the parent-copy cost per elite fight rose (metal +2.61
  against the plain seed's +1.43, inflame +1.54 against +0.65): stop. The
  card bursts' elite cost is not missing rehearsal; not followed, since a
  card burst repairs nothing @tsl1 (decisions "Copy-rehearsal stopped").
- Read 2026-11-07, jobs `0327`-`0332` (`measurement/burst8-tsl1@cells`):
  the three burst8 nets with the turn-start leaf against the 10-29 net's:
  Demon Form decks +0.48 (0.81) HP, train -0.68, other held-out -0.99.
  What burst8 learned there was the first tick; with the leaf the burst
  nets lose everywhere. `coverage-pretrain` folded into
  `generated-enemies-bench`.
- Read 2026-11-07, job `0333` (`measurement/turn-start-leaf@headline`):
  the turn-start leaf on the headline one turn deep, own picks, is level
  (+0.12 (0.48) HP, protocol fail), so the one-turn controls stay plain.
  Under it a +9.9 HP fighting gain on shared Demon Form decks and a -4.6
  HP cost on the 78 sequences where the chooser now also takes it cancel
  (`cause/chooser-horizon`, narrowed 2026-11-10 to the leaf repair).
- Read 2026-11-07: `0296`-`0298` (`measurement/fresh-control@cells`: the
  twins level on fresh sequences, so the control was no lucky draw) and
  `0299`-`0300` (80k level with 40k, `decision/no-goal2-training-arms`).
  The fresh-range file is the shared control for same-net reads (detects
  about 0.4 HP).
- Not queued: the HP price at 0.005, 0.0075 and 0.015 on the fresh
  control (every price so far moved under 1 HP; a one-turn gain reaches
  the product at a third).

9. **race-price**: merged into 51 (2026-11-10) as its Ritual 2 target
   (a growth-gated price on the enemy's HP is one case of a counterfactual
   price per persistent element); its evidence is cited there.

10. **hexaghost-headroom** (Source: navigator ideas run 2026-11-05; goal 2;
   a long shot): is there fighter headroom in the Hexaghost fight? A
   depth question, so it plays two and three turns deep. Mechanism:
   Hexaghost is half of the product's boss deaths over 1000 sequences (70
   of 140) and is lost in the fight: 44 of its 70 deaths arrive with 50 HP
   or more (`cause/boss-deaths`). Its threats are scheduled past two turns
   (a large multi-hit every seventh turn, Strength each cycle, Burns), and
   on the same decks at the same entry HP the second turn of search wins
   +0.083 (0.024) more Hexaghost fights than one turn, most of it at 40-59
   HP (`measurement/depth-by-boss@replay`), while bursts on Hexaghost games
   teach the one-turn leaf nothing. Closest technique: selective search
   extension, used here as a headroom measurement per fight kind, not as a
   product. The record: the depth family is closed
   (`decision/depth-family-closed`) on elites, where the metric was HP
   lost; this revives it for boss wins only. Rated **a long shot**:
   against, three turns bought no HP on elites (`cause/depth-saturated`),
   a boss fight three turns deep is slow (about 5 thread-min per elite
   fight, 8.2 GB at 3 threads), and a go gives no product this dev machine can
   read on the headline, only a target (a stronger teacher at the boss).
   Probe: `depth_probe.py play --kind boss --arm three` exists, but its 77
   Hexaghost fights detect about 0.11 against a hoped-for +0.045, so it
   does not run (the owner's detectable-effect rule); what would: both
   books' Hexaghost arrivals at 40-69 HP (about 190 fights, detectable
   about 0.07) through a per-boss filter of a few lines, about 40 thread-h
   at 2 threads and 5.5 GB. The most expensive probe on this list. The
   cheaper half of the same question failed (rows showing the next move
   taught nothing, `measurement/portfolio-pattern-rows-burst`); it waits
   for the review's answer on goal 2's CPU share (open question 7).
11. **boss-step-hp-price** (Source: navigator ideas run 2026-11-04; a long
   shot; goal 2): the fighter's HP price at the leaf (@hpe0.01, a constant
   per HP point) replaced by a price that follows the next boss's win
   curve, steep where that boss's step sits, near zero above 80
   (`cause/boss-curve`). The gauntlet knows the sequence's boss, so the
   price is a search-time setting per sequence, no training. Target: the
   Guardian alone (48 of its 57 deaths over 1000 sequences arrive under 60
   HP, win 0.92-0.97 from 60; `cause/boss-deaths`); Hexaghost's deaths do
   not follow entry HP. The HP goes at the two elites (17.3 and 13.8 per
   fight), which the product wins nearly always, and in a fight won for
   sure a steeper price picks the same line, so it can act only where it
   trades a little win chance at the elite for HP. Closest technique:
   reward shaping with a downstream value (decisions "Run value along HP:
   the plan", the "combat price by floor"). Not run-level decision work.
   Rated **a long shot**: every learned or re-shaped HP price so far
   gained at most ~1 HP (`decision/survival-score-closed`), the sim
   chooser already prices the boss, and the HP the product leaks in won
   fights is not recovered by more search (`cause/depth-saturated`). Code
   ~2 h (a per-sequence price in gauntlet.py); probe: one turn deep on 250
   headline sequences (~0.5 cpu-h); kill-fast: stop if Guardian deaths do
   not fall.
12. **parity-harness-level0**: answered elsewhere (2026-11-13): the real-game
    bridge's fidelity number (`docs/specs/real-game-bridge.md`) compares each
    predicted step with the installed game, behaviour included, on whatever the
    owner's live fights meet; sts_lightspeed stays a lead only
    (`decision/parity-source`). Reopens for content the live runs don't reach
    whose behaviour (picks, chance) is in doubt.
15. **new-mechanics-workflow** (ideas#51): extending engine and net as a
    repeatable workflow with checks (tiers A-C). Goal 1's backbone; large.
    Its engine half is the registry (`lane/runtime-registry`); its net
    half is the burst per mechanic family (about 100 games one turn deep,
    `measurement/adaptation-curve`), shipped as a net a content pack names
    (`decision/burst-adapted-column`); bursts compose one turn deep
    (`measurement/portfolio-sequential-bursts`), else new input atoms after
    stage 4. Related: ideas#71 (a larger tier-B set for zero-shot transfer
    as a standing goal-1 metric, which `generated-enemies-bench` builds).
16. **prior-art-card-ai**: open questions 4 and 5 (few-shot and continual
    adaptation of game-playing value nets; StS bots on content they were
    not written for; does sts-ironclad-agent, 50.1% A20 Heart over 501
    runs, peek at the draw order) plus the earlier scan on stochastic card
    games with hidden draw order (a prior-art scan). No CPU. The 2026-11-09 review's prior-art lens covered part of
    question 4 (replay ratio, AIVAT: `aivat-reads`); question 5 stays,
    run as a scan, not as a lane. A borrowed
    technique lists its preconditions before it becomes a candidate.

19. **ceiling-player** (Source: review 2026-11-06, direction 8; goal 2; a
    long shot): a search handed the fight's true draw order and monster
    rolls, played on the same cell sequences: an upper bound, with the
    product reported as its share of the distance from the heuristic to
    the bound, per floor kind. Mechanism: nothing on disk says how much
    headroom the fight has left; elites take 77% of the HP lost before
    the boss and three steps of player strength moved that by about 2
    HP each, which fits "forced by the deck" as well as "a blind spot
    every player shares". Closest technique: perfect-information bounds
    on imperfect-information play (double-dummy analysis in bridge; the
    "strategy fusion" literature on why such a bound is loose). The
    bound is loose, so only one outcome decides: a bound that also loses
    about 15 HP an elite says in-fight work is done and what is left is
    decks and the run layer; a bound far above says little. Rated **a
    long shot** that the decisive outcome appears; **even** that the
    change is small. Shown useless if the bound sits more than 10 HP an
    elite above the product. First step, no CPU: read
    `engine/src/search.rs` (`sample_rng`) and `runner.rs` for whether
    the search can be given the fight's own generator state; build only
    if it is a few lines. About 0.15 thread-hours per 500 cell sequences
    one turn deep.
20. **exact-referee** (Source: review 2026-11-06, direction 6; goal 1):
    small exactly solvable positions holding generated or pack content,
    solved in memory (`sts.solve` with `store=None`), with decision
    regret for the heuristic and the product one and two turns deep,
    split by how many untrained rows the state holds. Mechanism: every
    goal-1 card read so far scores the net against the heuristic, which
    values 37 of 43 generated test cards at zero; exact values need no
    reference player. Closest technique: endgame tablebases as an
    evaluation oracle; in this record the exact puzzles
    (`docs/research/exact-puzzles.md`), on official content only. Rated
    **even** that it builds within its cap (whether the solver finishes
    positions with generated powers inside its node budget is unknown),
    and its reach is short: positions a turn or two from the end
    under-sample powers that pay late, the one class with a measured
    cost, so it would mostly confirm that content landing inside the
    turn costs nothing. Shown useless if fewer than half of the
    positions finish at 1e6 nodes. 2-4 cpu-h under 2 GB. Cheapest probe:
    five endgame positions for each of the 40 generated test cards;
    count how many finish. After `act1-cards-zero-shot`, whose result
    says whether a referee is the missing piece.
22. **incremental-state-key** (Source: navigator ideas run 2026-11-06,
   from the sparse-state spec's speed case: about three quarters of a
   two-turn search copies, hashes and compares whole states; machine
   time; held until `sparse-state` lands): keep a 64-bit key in the state,
   updated at each mutation (HP, block, energy, a pile entry, a power),
   so the search's tables hash one word and reject unequal states by key
   before comparing bytes. Closest technique: Zobrist hashing in chess
   engines (Stockfish's position key); what differs: a combat state has
   many more mutation sites (every power and pile write, the RNG) than a
   board's piece moves, and the key must equal a fresh computation in
   every state, or golden and H4 break. The search's tables already use
   FxHash (`engine/src/search.rs`), so the cheap hasher swap is done; the
   solver's `StateMap` uses std's SipHash (`engine/src/solve.rs`), a swap
   the solver alone would see. Rated **a long shot**: for, hashing and
   comparing scale with bytes; against, after sparse-state the state is
   about 850 bytes, FxHash over that is tens of nanoseconds, and keeping
   a key right across every write site is a large, error-prone change.
   Shown wrong if hashing and comparing take under a fifth of search time
   on the sparse build. 0.2 cpu-h. Cheapest probe: a profile of
   `two_turn_phases 100` on the sparse build split into copy, hash,
   compare and the rest; one read: over a fifth goes on to a spec, else
   retire.

34. **sleeping-enemy** (Source: owner discussion, 2026-11-08, the owner's
   "{enemy}-vulin"; goal 1): any enemy starts asleep with Metallicize
   scaled by its max HP and more HP and damage, waking when it loses HP
   (Lagavulin's rule, with the Stun and the loss of Metallicize). Its parts
   are familiar (Lagavulin's, plain stats cost nothing,
   `measurement/wide-bench@one-turn`), so as a novelty bench it is mostly
   its own stat control; its value is as a read of setup turns: free turns
   reward playing powers that pay later, the place the net misprices
   (`measurement/mutated-cards@stage-a`). Elite parents are won 0.99, so
   read in HP. Blocked: waking is code for Lagavulin only
   (`engine/src/state.rs` 1829); needs block M2, a move switch on an
   event (`docs/research/act1-inventory.md`), which `act1-content` needs
   for Lagavulin and the Guardian as data. Rated **a long shot** for a
   cost; waits for M2, then about 1 cpu-h.

35. **ascension-levels** (Source: owner discussion, 2026-11-08; goal 2,
   the ruler; goal 1's custom content): the engine plays ascension 0
   today (owner). An "upgrade" form for enemies like a card's upgrade
   link: per monster, the ascension tiers' changes (higher damage, higher
   HP, changed move patterns and elite or boss extras, from the wiki and
   sts_lightspeed per `decision/parity-source`) as fields of its content
   entry, and an ascension setting for fights and runs (the player-side
   levels, as Ascender's Bane and lower max HP, beside them). Why: a
   dominant StS AI is judged at high ascension, and the headline's
   0.78-0.81 clears is at ascension 0; the pick and play advice the
   project has measured can change with level (the owner rarely takes
   Demon Form at high ascension). Evidence: plain stat changes cost the
   net nothing beyond the heuristic (`measurement/wide-bench@one-turn`),
   so the stat tiers need no adaptation; pattern changes may. Not
   reviewed with a sceptic yet. Waits for `act1-content`'s monsters as
   data (an upgrade field on a code-held monster is double work). Rated
   **likely** buildable as data for the stat tiers; patterns need M2-like
   blocks. CPU: a headline read at a chosen level, about 3.5 cpu-h.

36. **fight-leaf-tsl1**: merged into 75 (2026-11-13) as its (a), job 0966
   (`gauntlet.py --chooser` was its step 1; `decision/tsl1-fight-leaf`).

41. **character-as-data** (Source: review 2026-11-09, direction 3; goal
   1's "a new character" as first-class custom content): the character
   (starting deck, relic, HP, card pool, `engine/src/character.rs`) as a
   content file, checked by re-expressing the Ironclad golden-identical
   and loading the Silent's writable cards (47 of 75 with today's
   vocabulary, `docs/research/second-character-census.md`). Mechanism:
   goal 1's custom content today stops at cards, powers and monsters; a
   character as data is the last kind the owner's goal names. Rated
   **likely** to build. Its block is gone: the relic kind (R1) and the
   relic entity landed on main (2026-11-11), so a starting relic can be
   data. Held for now: it edits the engine files the owner's Act 1
   sessions change daily (`engine/src/character.rs`, relic loading;
   `decision/act1-owner-led`), and a role lane building beside them would
   race their landings; it becomes a project-slot candidate when the
   owner's Act 1 work pauses or the owner asks for it. About a day of
   code, under 1 cpu-h.

43. **reserve-from-peak** (Source: navigator ideas run 2026-11-09, from
   `queue-throughput`'s close and `measurement/queue-backfill-replay`;
   machine time): `jobs.py add` warns and records `mem_gb_high` when
   `--mem-gb` is over 1.5x the same command kind's last peak (symmetric
   with today's `mem_gb_low`, `how/job-admission`), and the runner may
   admit a job that waited an hour on memory at 1.25x that peak.
   Mechanism: 0565 reserved 4.0 GB against a 0.97 peak, 0204 3.5 against
   2.47, 0276 5.0 against 3.81, each the only runnable job while 3-5 GB
   was free; the runner wants `mem_gb` + 1 free. Closest technique:
   memory requests sized from job history in batch schedulers (Slurm's
   seff-style right-sizing); what differs: no cgroup limit enforces the
   reservation, so an under-reservation pages other processes instead of
   killing the job. Rated **likely** to build, **even** that it recovers
   2 h or more on the replay (oracle bound about 3.9 h over 3.6 days, with
   peaks known after the fact; a burst's peak varies 2.8-7.4 GB with its
   arguments, so a kind's last peak can mislead). Shown wrong if the replay
   with reservations at 1.25x the kind's last peak recovers under 2 h.
   About 1-2 hours of code, no CPU. Cheapest probe: `scripts/queue_replay.py`
   with that reservation rule (a flag to add), one read; kill-fast: under
   2 h, stop. Not opened 2026-11-09 (decisions "After queue-throughput's
   close"): about an hour a day at best.
   New evidence (learn-memory's close, 2026-11-09): the runner's
   `peak_gb` is the process tree's working set, mapped feature-cache
   pages included (6.06 GB against 1.01 GB commit for a 40k learn), so
   peaks of learns and cache readers overstate what they reserve; the
   commit half of this idea is `pack-net-scratch`'s step 0 when its learn
   holds other jobs out. Review 2026-11-10 (skeptic-checked): about half
   of the idle hours since 11-03 had a ready job held back; memory held 27
   distinct jobs (reservations inflated by mapped feature-cache pages,
   some `mem_gb` set by hand), the heavy-slot cap 81 (operating.md's
   machine limits, not this candidate's). Moves up beside 54. Review
   2026-11-11 (skeptic-checked): since 11-03 a heavy slot held back 108
   jobs against memory's 39, both slots were full 64.5 h against 32.5 h
   idle while work waited, and the median job peaks at 0.55 of its
   `mem_gb`; so a third heavy slot when free cores and memory allow (the
   runner measures both) belongs in this entry's replay too
   (`scripts/queue_replay.py` has a heavy-slots flag). The commit half
   now has a cost on record twice: on 2026-11-11 (0817) and again on
   2026-11-12 (0899, 0904) a lane followed `add`'s `mem_gb_low` warning to
   mem_gb 5.5 on a 40k learn that commits about 1 GB, the job could never
   start, and the machine sat idle about 1.5 h with 18 jobs waiting until
   the navigator re-queued them at 2.5 (decisions "Learns 0899 and 0904
   re-queued at mem_gb 2.5"). `how/job-admission` now names the
   exception, but the warning still says the opposite: the cheapest fix is
   that the runner records peak commit beside the working set and `add`
   warns from commit. Tooling for a lane worker while its lane waits on
   CPU; the first lane worker with an idle hour takes the commit half.

45. **value-chooser-path** (Source: owner discussion, 2026-11-09,
   `/approach`; goal 2, and goal 1's own-pick reads; asked into the queue
   by the owner): the value chooser (`--rewards value`) scores each option
   on every encounter the sequence can still meet and on no dealt hand.
   (a) Path awareness: the horizon is every hallway encounter of a pool
   with a floor still ahead, every elite not yet fought while an elite
   floor is ahead, and the sequence's own boss; each encounter once,
   weighted by its chance of being met (today: the next floor's 8-draw,
   all three elites and the boss at 1:1:1, `scripts/gauntlet.py`
   `value_parts`, so floors 7, 8 and 10 never count from floor 4). Future
   acts add their pools the same way. (b) No card-draw evaluation: each
   start state is valued before the opening hand is dealt, not over
   seeded hands (`--value-hands` goes); the plain one-turn leaf the net
   is trained on is the state at the next turn's draw
   (`cause/unseen-cards-half-edge`), so a pre-draw state is in its range.
   Needs a start state without the dealt hand (today `sts.Combat` deals
   it at construction). Mechanism: picks follow the whole path the run
   can still meet, not one floor's draw, and carry no hand or seed luck;
   the value chooser stays cheap (owner: an exact-over-hands chooser has
   no place; the long-run aim is the AI making run decisions). In this
   record: level with the sim chooser overall at a sixth of the wall
   time, +4 to +5 HP on train-card sequences, -4 HP on held-out ones
   (`measurement/value-chooser@headline`, `decision/value-chooser-use`).
   Rated **even**: the horizon change is unmeasured and the pre-draw
   value is untested. Shown wrong if it reads below today's value
   chooser on train-card sequences 0-499 at 2 se. About 3-4 h of code
   (gauntlet.py, a pre-draw start state in `py/`), reads about 0.25
   cpu-h each one turn deep. Folded in 2026-11-10: `elite-horizon-chooser`
   (the sim chooser's horizon plus the elite pool); its evidence, the
   leaf repair's Demon Form overpick, does not hold for a net that
   learned the card (`cause/chooser-horizon`), and the path part here
   holds every elite ahead by construction. A chooser change: run-level decision work,
   so it runs when Act 1's cards are in, beside the wider headline
   (decisions "Headline card pool and choosers after Act 1").

52. **random-world-product**: merged into 60 (2026-11-11) as its step 2
   (the k-4 random-world bench two turns deep); its evidence is cited
   there.

54. **read-preflight** (Source: review 2026-11-10, direction 1 as its
   skeptics corrected it; machine time): `jobs.py add` of a read that
   names `--against` prints the expected paired sd for its pair type
   (`yardstick/read-floors`), the floor at its sequence cap and Wald's
   average sample size at its H1, and warns when `--min-n` equals
   `--sequences` (sequential stopping off: 201 of 216 gauntlets since
   11-03 could not stop early). Mechanism: about 36% of queue CPU since
   10-30 ended inside noise, most of it predictable from the floor before
   the run, which is computed by hand today. Closest technique: power
   analysis before an A/B test; fishtest's SPRT bounds. Rated **likely**
   to build, **even** that its replay over jobs/done since 11-03 would
   have flagged three or more past fails without flagging a winner
   (two-turn, sim-boss). About 1-2 hours of code, no CPU; kill-fast: the
   replay, one read. Tooling: a lane worker builds it while its lane waits
   on CPU; no lane of its own.

55. **chooser-noise** (Source: review 2026-11-10, direction 8, the
   strength lens; goal 2's ruler, `cause/headline-pairing-weak`):
   re-score the floor-0 to floor-2 offers of 200 headline sequences with
   the same sim chooser under 5 trial-fight seed bases, counting how
   often the pick changes and how often the top two sit within one se.
   Mechanism: decks diverge between nets after floor 1 (identical decks in
   0-3 of 250 sequences; pairing buys 1.2x on the headline against 4x on
   fixed decks), and 7.5-18% of first picks flip between near-identical
   trial players; if picks are mostly trial-fight noise, shared or more
   trial seeds keep decks together between players, raising pairing and
   lowering the 2.5 HP between-net floor of every goal-2 read. A check of
   the ruler, not new run-level decision work (the Avoid item; decisions
   "After the big-picture review of 2026-11-10"). Closest technique:
   common random numbers in simulation-based choice. Rated **even** that
   more than 25% of first picks flip; shown wrong under 10%. About an
   hour of code (a seed-base argument to the chooser's scorer), 0.1-0.3
   thread-h; kill-fast: one read. Goal 2 (0.2 of development weight):
   behind the goal-1 entries, a probe-sheet read once its flag exists.

59. **control-arm-cache**: merged into 66 (2026-11-12) as its part (b).

61. **sparse-feature-cache**: merged into 66 (2026-11-12) as its part (a).

62. **name-free-atoms** (Source: review 2026-11-11, the generalisation
   lens and the skeptics of its claim 5; goal 1's first-class custom
   content): describe a trigger or effect to the net by what it does (a
   fingerprint of its consequences: HP, block, energy, cards and powers
   it changes, measured by running it in the engine on probe states)
   instead of by a one-hot name. Mechanism: a brand-new atom is an
   untrained input column under names, so a custom mechanic built on one
   cannot transfer zero-shot however wide the pool; a consequence
   fingerprint puts it near the atoms it acts like. Closest technique:
   behaviour-based embeddings of actions and items (action embeddings
   from effects, Chandak et al. 2019; zero-shot card representations in
   Hearthstone agents); in this record `simulated-effect-inputs` was
   checked and not proposed on cards (in-turn content was free), which
   differs: this targets an atom inside a mechanic that recurs. Rated **a
   long shot** (against: in-turn atoms cost nothing already, and
   WeakOnHit's untrained trigger was cut 78% by a burst on a related
   mechanic; and 0898: the generated-pack net cuts mechanics built on a
   trigger or effect no enemy power in its pool had by 0.60-0.81, because
   the inputs already describe atoms through columns other content trains,
   Flame Barrier for Attacked, Sentry's status cards for Wound, spec
   `docs/specs/wider-generators.md` Amendment 1; the one uncut kind, deck
   effects, has trained columns too, so a fingerprint would not reach it).
   Waits for `column-zeroing` (the probe sheet; once `wider-generators`'
   step 2b, which left the lane 2026-11-13): if zeroing the trigger or effect
   column costs the generated-pack net under 1 HP on the held-out rows,
   names carry little and this is retired; over 2 HP, it is worth a
   design.

64. **state-coverage-scratch** (Source: navigator ideas run 2026-11-11,
   from 0898 (the generated-pack net cuts mechanics built on atoms no enemy
   in its pool had, 0.60-0.81, and leaves deck effects uncut),
   `leaf-blind-numbers` (a Strength below zero, which training never
   shows, is mispriced at the leaf) and `jitter-training`'s rejection;
   goal 1, a cheaper and wider base net for custom content): a from-scratch
   learn on official content only, its fights started from randomised
   statuses (player Strength and Dexterity from -3 to +3, Weak, Vulnerable
   and Frail stacks on either side, monster Strength, HP spread), against
   the generated-pack recipe on the 24 old rows and the wide rows.
   Mechanism: one turn deep the search plays an enemy power in the engine
   and the leaf prices the state it leads to; if what the generated pool
   taught is to price such states (reading (b) in decisions "After 0898"),
   random statuses give the same coverage with no generator, and they
   cover custom content by the states it reaches, not by its names; deck
   effects stay out (their cost lands on later draws). Trade-off: the
   generated pool gains if the net reads the power row (reading (a)) or
   needs the timing of punish triggers; the random statuses gain if
   coverage of states is the lever, at no generator cost and with every
   official fight still in the pool; each can win. Closest technique:
   domain randomisation (Tobin et al. 2017) and exploring starts in
   reinforcement learning; in this record `jitter-training` (stat shifts on
   monsters in a 400-game burst on a trained net, shown wrong,
   `measurement/stat-burst@one-turn`). What differs: from scratch, player-
   side statuses, read where the generated pool's cut is measured. Rated
   **a long shot** until the row ablation reads (b), **even** after (for:
   the uncut deck effects fit (b), and leaf-blind-numbers' unseen number;
   against: the stat burst taught nothing, and the generated pool's
   training rows are cut 1.29, more than its held-out rows, which fits
   reading the row). About half a day of code (status randomisation in the
   learn's game generator), about 16 thread-h for the learn and 6 for the
   reads: about 22. Cheapest probe: the whole-row ablation inside
   `wider-generators`' step 2b (about 1 thread-h, already chartered);
   kill-fast: the cut keeps under a third of itself with the row zeroed,
   retire this (the net reads the row).

65. **wide-recipe-confirm** (open as `lane/wide-recipe-confirm` (2026-11-13); Source: navigator ideas run 2026-11-12, from
   `wider-generators`' step-3 files, read early by the navigator before the
   lane's own read: one seed of the wide recipe (widepack40k s1, 58
   training mechanics over 9 triggers and 12 effects) leaves +0.25 (0.15)
   HP beyond parent on the 17 new held-out pairs (cut 0.94 (0.04) against
   pack-net-scratch s1, 0.84 (0.09) against the 18-mechanic net), +0.52 on
   the whole held-out trigger Attacked (cut 0.91 against pns1), +0.05 on
   the whole held-out effect Wound, and +0.10 (0.15) on the old 6 held-out
   pairs (cut 0.98 (0.03) against pns1); training rows level with the
   18-mechanic net's (-0.23 (0.15) HP); and from the owner's yardstick
   (`measurement/genpack-yardstick@18-seeds`): pooled novelty cost +0.92
   (0.19) HP against pns1's +4.03, where the 18-mechanic nets read +0.96 /
   +2.27 / +2.01 over seeds 1 / 101 / 201; goal 1, the recipe as goal 1's
   base net, and goal 1's standing number): seeds 101 and 201 of the wide
   recipe read on the same row sets and the yardstick, on an encoding that
   shows every power it trains on (step 0). Mechanism: a single
   seed is a lead (`docs/operating.md`, "Reading results"), and every later
   goal-1 step (bursts from this base, 63; multi-hook powers, 68) builds on
   it; on the grid the 18-mechanic recipe's three seeds spread 0.81 / 0.68
   / 0.78, and on the yardstick 0.96 / 2.27 / 2.01, where seed 1 was the
   best seed of both recipes (wide s1 0.92), so the yardstick is where a
   seed-1 lead most likely shrinks. Trade-off: none to probe (a
   confirmation with a fail condition); the yardstick also says whether
   the wide grid adds to the 18 mechanics there (descriptive, against
   their three-seed pool of 1.75). Closest technique: seed replication
   (the project's own rule); in this record `generated-pack-scratch`'s
   three seeds. Rated **likely** on the grid (for: the 18-mechanic recipe
   held over three seeds; the wide cut is large against its se; the
   6-mechanic arm cuts the old held-out rows 0.88 against the 18-arm's
   0.81, so fewer games per mechanic does not weaken the held-out cut,
   `measurement/mechanic-count@six-arm`; against: one seed, and the wide
   net's parent edge on official elites is 0.63 (0.26) HP below pns1's,
   inside the 18-mechanic seeds' -0.91 to +0.59), **even** on the
   yardstick's go bar (the 18-mechanic seeds 101 and 201 sit at or above
   half pns1's cost). About 6 thread-h a learn (0926: 60 minutes at 6
   threads, peak 6.8 GB, so a learn waits for about 8 GB free, less after
   66's sparse cache), about 10 for a seed's full reads (0916-0919's
   records) and 1 for its yardstick read (0931: 10 minutes at 3 threads):
   about 17 a seed. Step 0 (candidate 71, `roundend-rows`, folded in
   2026-11-13, decisions "After the filler hold"): a generated `RoundEnd`
   power gives the net no input row (`cause/roundend-blind`), so a twelfth
   of the wide pack's mechanics train a net that cannot see them; the fix
   writes a `RoundEnd` hook that isn't a pure `ReduceSelf` countdown as a
   `triggered` row and counts it in `is_hook_power` (no official input
   changes: `series_check` on the product net), then relearns seed 1 on
   it. About 51 thread-h with step 0 passing (three fixed seeds), 44 if
   it fails (seed 1 stays the old file). Cheapest probe: step 0's learn
   read on the wide grid's rows; kill-fast as in the stop rule. Candidate
   70 (`wide-full-triggers`) left this charter
   (2026-11-12): its one-seed pick on thorns2 sits inside the 18-mechanic
   seeds' 2.45-6.28 HP spread on that row.
   Charter (opened 2026-11-13, `lane/wide-recipe-confirm`; decisions "13-14 Nov",
   binds its queueing: nothing queued on the 13th evening that would not
   end by 14 Nov 08:00): goal: goal 1, whether the wide generated recipe's
   zero-shot cut on unseen enemy pairings and on the owner's yardstick
   holds across training seeds, as the base net for later goal-1 steps,
   on an encoding that shows the net every power it trains on; measure:
   step 0 (code) a `RoundEnd` hook that isn't a pure `ReduceSelf`
   countdown written as a `triggered` row and counted by `is_hook_power`
   (a test: a GE-RoundEnd power writes one triggered row; `series_check`
   PASS, the product net bit-identical), then seed 1 of the wide recipe
   relearned on it (configs as widepack40k-s1, 40k games) and read @tsl1
   one turn deep on the wide grid's rows (675 official elite starts x 2
   seeds) against `gen-wide-wp1-tsl1.json`: the RoundEnd rows apart, the
   rest pooled; then per seed (1 if step 0 passed, 101, 201) the wide
   grid's new rows, the 24 old rows (x 4 seeds), the yardstick rows as
   0931 (`docs/research/genpack-yardstick.md`, same mods, 675 x 2), cells
   and pack headline against the seed-1 controls; pooled over the three
   seeds of the wide recipe's held-out rows against pack-net-scratch s1
   (and its s101/s201 files where they exist), the yardstick also against
   the 18-mechanic three-seed pool (descriptive); stop: step 0 passes if
   the RoundEnd rows' pooled cost beyond parent falls by 1 HP or more at
   2 se and the other rows are not worse by 0.3 HP at 2 se (seeds 101 and
   201 then train on the fixed encoding); else seeds 101 and 201 train on
   the old one and the fix stays in code as a correction; go if the
   three-seed pooled new held-out cut is 0.7+ at 2 se, the old held-out
   not worse than the 18-mechanic three-seed pool at 2 se, the
   yardstick's pooled cost over sharp2, thorns2, ritual2, weakhit1 at
   most half pns1's (+4.03) at 2 se, and cells and pack headline within
   -1.5 HP; fail if the pooled cut is under 0.5, a seed's cut under 0.3,
   or the yardstick's pooled cost over half pns1's (the seed-1 result was
   luck); kind: project; cap: 76 cpu-h; end: 2026-11-20; on-close: wake
   always.

66. **machine-throughput** (closed 2026-11-15 before it started, comes back when a second slot opens; Source: review 2026-11-12, direction 2;
   merges 59 `control-arm-cache` and 61 `sparse-feature-cache`, which
   three reviews filed as "a lane worker builds it while its lane waits"
   and nobody built; machine time, both goals): one project lane whose
   charter is the machine. Parts, each checked by a program: (a) the
   learn's feature cache stored sparse (61: 8.3-8.8 GB dense at 2-5%
   nonzero, round-0 epochs 46 s in RAM and 150-880 s from disk; the wide
   learn 0926 peaked at 6.8 GB against a 2.5 GB reservation, beside which
   0908 stalled 2.5 hours); (b) the control-arm cache (59: about 30
   thread-h of byte-identical heuristic arms replayed); (c) the stall
   check reads a job's `.partial` progress file when its log names one
   (0929/0930 showed STALLED while writing every minute); (d) admission:
   whether a third heavy slot (or admission by measured idle cores and
   free memory) shortens the queue, replayed first with
   `scripts/queue_replay.py` over `jobs/done` since 11-04 (it needs a
   slot-count option, which it lacks today),
   adopted as a decisions entry on the owner's behalf only if the replay
   recovers 2 h or more (the reopen condition of `queue-throughput`);
   (e) `test-full` files run 3-4 at once inside its 4-thread budget (no
   full run has passed since 11-10). Mechanism: the runner logged 181
   waits for a heavy slot against 44 for memory, booked threads average
   about 30% of the machine's threads. Closest technique: build caches keyed
   by input hashes (the ladder's `.pyd`-keyed caches,
   `how/ladder-champion`), CSR storage in tabular learners, backfill
   scheduling; in this record `queue-throughput` (closed: backfill alone
   recovered 0.0-1.1 h, the idle was job size and reservations), which
   this differs from by changing job size and reservations, not order.
   Rated **likely** to build parts (a)-(c) and (e), **even** that (d)
   passes its replay; the measured gain is the exit target below. About
   4-6 thread-h of checks plus one confirming learn (about 6). Cheapest
   probe: under a minute on one thread, a sparse copy of 200k cache rows
   and 100 random 512-row gathers timed against the dense memmap, cold
   and warm; kill-fast for (a): sparse gathers slower than 2x dense warm,
   drop (a) and keep the rest.
   Charter as opened (`lane/machine-throughput`, on-close wake on fail): goal: machine time for
   both goals: more decided reads per day from the same dev machine; measure:
   (a) a 40k learn's feature cache sparse, batches bit-identical to the
   dense cache (a test), the confirming learn's wall time and peak commit
   against 0926 (60 min, 6.8 GB); (b) the control-arm cache in
   `mutate_monsters.py` keyed by the `.pyd` hash and the arm's spec, a
   cached arm byte-identical to a re-run (a test); (c) the stall check
   reading `.partial` progress (a test on 0929's log and file); (d)
   `queue_replay.py` with a slot-count option, 3 slots over jobs/done
   since 11-04, adopted
   only if it recovers 2 h or more; (e) `test-full` with files in
   parallel inside 4 threads, and one full run passing or naming its
   failures; stop: go when (a) cuts the learn's wall time by a fifth or
   its peak by a third with identical batches, and (b) and (c) land
   with their tests; fail if (a) is slower or not identical and (b) does
   not land (then the parts that landed stay, and the lane closes);
   kind: project; cap: 15 cpu-h; end: 2026-11-16; on-close: wake always.

68. **multi-hook-zero-shot** (Source: review 2026-11-12, direction 6;
   goal 1's first-class custom content): the wide net zero-shot, @tsl1
   one turn deep, on about 20 generated enemy powers with two or three
   hooks and a condition each (built from the grid's atoms, none in the
   wide pack), against pack-net-scratch s1, with a 50-100 start subsample
   two turns deep as a column that does not lean on the heuristic.
   Mechanism: real custom content holds several hooks per power, while
   every generated row on record has one; if the wide net's features
   compose, its cut holds on a power whose parts it saw apart (the k-4
   random worlds composed across monsters, `measurement/genpack-reach@stacks`,
   but never inside one power). Trade-off: the wide net gains if parts
   compose inside a power; pns1 cannot gain on content it never saw, but
   the read can show the cut falling toward it; and the heuristic, blind
   to most generated hooks, may read a composed power as easy, which the
   two-turn column checks. Closest technique: compositional
   generalisation (SCAN, Lake and Baroni 2018); in this record the random
   worlds (several powers, one hook each). Rated **even** (for: stacks
   composed at four fifths of the singles' cut; against: a condition is a
   new input kind for an enemy row, and a hook that changes what another
   hook sees is a new interaction). Needs a small generator change (two
   hooks per power in `gen_enemy_pack.py`'s bench rows), about half a day
   of code; about 4 thread-h for the reads. Kill-fast: the wide net's
   pooled cut on the multi-hook rows against pns1 under half its cut on
   single-hook held-out pairs (0.94), at 2 se: composition is the next
   gap, and a multi-hook training pack follows.
   Opens once 65's seed-101 grid read is recorded, so it builds on a
   base read on two seeds.
   Held charter (not ready while one lane runs, `decision/one-lane`;
   ready again for the first project slot after `lane/final-round`): goal: goal 1's first-class custom content, whether the
   wide recipe's zero-shot cut holds on enemy powers with two or three
   hooks; measure: about 20 generated enemy powers with two or three hooks
   and a condition each, built from the wide grid's atoms with no
   RoundEnd hook (blind until 65's step 0) and none in the wide pack (a
   bench-row option in gen_enemy_pack.py / mutate_monsters.py), the wide
   net s1 and s101 @tsl1 one turn deep on 675 official elite starts x 2
   seeds against pack-net-scratch s1 and s101 on the same rows, cut per
   row beyond parent, pooled over rows and the two seed pairs; a 100-start
   subsample two turns deep (wide s1 against pns1) as a column that
   doesn't lean on the heuristic; stop: go if the pooled multi-hook cut is
   0.7 or more at 2 se (parts compose inside a power: multi-hook rows join
   the standing bench); fail if it is under 0.47 (half the single-hook
   held-out cut, 0.94) at 2 se (composition is the next gap: a multi-hook
   training pack is the next candidate); between, descriptive, the per-row
   spread names the hard combinations; kind: project; cap: 6 cpu-h; end:
   2026-11-22; on-close: wake always.

69. **clears-statistic** (Source: review 2026-11-12, direction 1 and its
   key claim 2; goal 2's ruler): the goal-2 accept or reject statistic
   tied to clears (plain clears, or boss-replay clear probability with 0
   for an earlier death), boss HP left reported beside it. Mechanism: the
   review re-split the strongest open candidate: the all-content twin's
   +1.41 (0.45) HP two turns deep is +1.32 HP left at the boss on
   sequences both players clear and +0.09 from clear flips, +0.014
   clears; a real effect (two turns over one) splits +3.68 flips and
   +2.45 HP left. HP left after the Act 1 boss is worth what the act
   transition leaves of it, which the engine's rules do not yet say.
   Trade-off: end HP gains where a change saves HP in won runs that later
   acts would spend; clears gains where only clears matter; each can be
   right, and the act-transition heal decides how much. Closest
   technique: fishtest's game outcome (win/draw/loss) as the SPRT
   statistic, not engine eval; in this record `yardstick/protocol`
   (end-HP SPRT) and `cause/ruler-below-goal` (each ruler dropped one
   stage of the objective). Rated **likely** that the offline replay
   finds most recent "passes" rest on HP left, **even** that it changes a
   decision: goal 2 has no candidate in flight (fighter swaps and recipe
   arms are off, `decision/crossed-player-lead`, `decision/no-goal2-training-arms`).
   No CPU: replay `gauntlet_protocol.py` over the last 10-15 against-reads
   on end HP and on clears, count the passes that rest only on HP left on
   sequences both clear, and look up the act-transition heal in the
   decompiled game code (`decision/parity-source`). Kill-fast: if no
   recorded pass or fail flips, keep end HP and file the split as
   `cause/` evidence. A protocol change itself is a decision on the
   owner's behalf only after the replay, since `yardstick/protocol` is
   what every goal-2 read cites.

70. **wide-full-triggers** (Source: navigator ideas run 2026-11-12, from
   `measurement/genpack-yardstick@18-seeds` (the wide net's yardstick cost
   is almost all Thorns 2, +4.20 HP on every elite, level with the 10-29
   net, while Sharp Hide is repaired) and the wide grid's own rows (0916:
   GE-Attacked-Damage +2.34 (0.28) HP is the Attacked row the wide net
   cuts least, GE-OppAttack-Damage +0.77); goal 1's standing number): the
   wide pack with its whole held-out trigger (Attacked, 11 mechanics) and
   whole held-out effect (Wound, 8) moved into training, the 17 new and
   6 old held-out pairs kept out, one from-scratch learn on seed 1.
   Mechanism: Thorns is Attacked-PlainDamage; Attacked is the one trigger
   no generated enemy in the wide pack carried, and damage that comes back
   per hit is priced past the turn (an attack-heavy hand keeps paying on
   later turns), which the leaf learns only from games that hold it
   (`cause/novelty-is-horizon`); Sharp Hide, an unseen pairing of two
   trained atoms, was repaired whole. Trade-off: the full-trigger pack
   gains if trigger coverage is the lever (Thorns' 4.2 HP); the wide pack
   gains if the extra 19 mechanics dilute its games (each mechanic gets
   about three quarters of its share) or if Thorns' cost is something
   else (the stack of 2 per hit, twice the grid's 1); each can win; the
   wide pack also keeps the whole-trigger measurement, which the full
   pack gives up (the yardstick and the 23 held-out pairs stay). Closest
   technique: coverage in procedural training content (domain
   randomisation, Tobin et al. 2017); in this record the 18-to-58
   mechanic step itself (`wider-generators`), which repaired Sharp Hide.
   Rated **a long shot** (for: Attacked is the one trigger the wide pack
   held out, and every unseen pairing of trained atoms is cut 0.9+;
   against: the wide net already cut the generated Attacked rows 0.91
   against pns1 without training the trigger, and the 18-mechanic nets,
   which train no attack-hit trigger either, read thorns2 at +2.45 /
   +6.28 / +4.62 over three seeds (`measurement/genpack-yardstick@18-seeds`):
   Thorns' cost moves about 1.9 HP with the training seed alone, so the
   wide net's +4.20 is not shown to be a coverage gap). About 6 thread-h a
   learn and 3 for its reads, half a day of code (a pack-writer option);
   a decisive read needs three seeds an arm against 65's three wide
   seeds, about 27 thread-h. Out of 65's charter (2026-11-12). Kill-fast,
   if ever run: the three-seed thorns2 pool not 2 se below the wide
   recipe's three-seed pool. Revisit after 65's seeds: if the wide
   recipe's thorns2 pools at +4 HP or more over three seeds while sharp2
   stays repaired, the gap is real and this rises to even.

71. **roundend-rows** (folded into 65 as its step 0, 2026-11-13; Source:
   navigator ideas run 2026-11-13, from a re-split of the step-2/3 files and
   a read of the encoder, `docs/research/generated-enemies.md`, "RoundEnd
   rows: the power is invisible to the net"; goal 1, first-class custom
   content): write a `RoundEnd` hook that isn't a pure `ReduceSelf`
   countdown as a `triggered` row and count it in `is_hook_power`.
   Mechanism: today such a hook is written only as the opt-in `countdown`
   kind, which no net turns on, so a power whose only hook is `RoundEnd`
   gives the net no row (`cause/roundend-blind`); the net then prices its
   damage, debuffs or Strength as if absent, as pns1 prices untrained
   turn-trigger damage (+2.8 HP), and no amount of training on it helps.
   Official content uses `RoundEnd` only for self-countdowns, so nothing
   official changes. Closest technique: an input-coverage check (a schema
   test that every content element reaches the model's features); in this
   record `how/burst-inputs` (atoms the net never read) and decisions
   "Series row kinds are opt-in", whose rejected alternative (new kinds on
   by default "since no spec in the series trains a net") no longer holds:
   from-scratch learns now train the base nets on generated content. Rated
   **likely** (for: nine trained RoundEnd mechanics cut 0.00-0.23 where
   trained turn-trigger damage is cut to about 0 at similar exposure; the
   code path shows no row; against: the triggered row's `RoundEnd` column
   is trained only by these nine mechanics, no official content, though
   the turn-trigger columns were learned the same way from the 18-mechanic
   pack). About 17 thread-h (one learn and a seed's reads) inside 65.
   Kill-fast: step 0's rule in 65's charter.
72. **blind-row-kinds** (closed 2026-11-15 before it started, comes back when a second slot opens; Source: navigator ideas run 2026-11-13, from
   `cause/roundend-blind` and the opt-in decision; goal 1, first-class
   custom content: a new mechanic should reach the net without a layout
   change): find every content element a custom power or monster can use
   that writes no row under the default kinds (triggered, threshold,
   held). From the encoder, likely candidates: a power with only static
   modifiers (not a hook power and not one of the 8 named
   `MODIFIER_POWERS`), only replacements or only rules, and a custom
   debuff's `ReduceSelf` countdown (its duration). Mechanism: an atom the
   net never reads can't transfer however wide the pool (the RoundEnd
   case shows the size: about 2 HP per elite fight, untouched by
   training). Closest technique: the same coverage test, the way
   `engine/tests/wording.rs` names an element missing from
   `content/wording.json`. Rated **likely** that it finds and fixes a
   blind element beyond RoundEnd: the engine audit
   (`docs/research/engine-audit.md`, entries 9 and 14, read only)
   already names nine effect atoms that write no column (BlockAlly,
   ApplyPack, Heal, HealOf, GainMaxHp, DrawPicked, PlayTop, Discover,
   ObtainRandomPotions), one of them official Act 1 content (Shield
   Gremlin's Protect intent reads as empty), and says why "no column"
   keeps winning: the contract pins hash whole-layout bytes, so every
   added column is a re-pin; its clean model (pins compared per named
   column) makes each fix cheap, and is the lane's natural first code
   step. Cheapest probe: a test over
   `registry::element_names()` that builds a one-element power per
   element and asserts the default encoder writes a row for it; kill-fast:
   no element blind beyond RoundEnd closes it as filed. For each blind
   element found, the fix writes the row the element needs without the
   official rows the opt-in kinds would add (their memory cost, the
   opt-in decision's reason), then a wide-grid row on it is read before
   any training. Charter: `lane/blind-row-kinds`.
73. **fresh-column-burst** (Source: navigator ideas run 2026-11-13, from
   `measurement/gbb@g11` with the wide net's zero-shot Artifact rows and
   `how/burst-inputs`; goal 1, few games to adapt on first-class custom
   content): a generated enemy power on an effect atom whose input column
   no content the wide base trained on ever wrote (none of the official
   content, the 100-mechanic wide pack or the decks), read zero-shot from
   the wide net s1 and after 33-game joint bursts (replay share 0.9, @tsl1,
   three seeds), with the burst's vocabulary widened to the new column
   (finetune.py keeps the parent's vocabulary for generated packs today,
   so the burst would be blind to it). Mechanism: the 11-game go bound a
   column that official content had trained (Artifact: Sentries) to a new
   pairing; the wide base has that case zero-shot (+0.29 HP). A custom
   mechanic built on a brand-new atom starts from an untrained column, and
   only the burst's own games can train it; whether 33 games are enough
   is goal 1's number for the case a new character or mechanic brings.
   Trade-off: the burst gains if the pool-trained trunk lets a fresh
   column bind from few games (as gp's trunk bound Artifact); it can't if
   the column needs more gradient than 33 games give, which the read shows
   as a cut under a third; the zero-shot net gains nothing here by design,
   so the probe first checks there is a cost to cut (a fresh atom whose
   effect lands inside the turn costs nothing, `measurement/act1-cards@zero-shot`).
   Closest technique: few-shot adaptation with new input features
   (fine-tuning a new embedding row on a frozen or shared trunk, as in new
   token embeddings for language models); in this record 62
   (`name-free-atoms`, which aims at the zero-shot case) and the
   pattern-rows burst (`measurement/portfolio-pattern-rows-burst`: new
   next-move rows taught nothing in 400-1600 games, a fresh row kind, not
   one column of a trained kind). Rated **a long shot** at 11 games and
   **even** at 33 (for: the gp trunk bound a new pairing in 11, WeakOnHit's
   unknown trigger slot was cut 0.78 by a related burst; against: the
   pattern rows, a fresh input, taught nothing at 1600 games, and the
   pool-less base got worse at 11). Follows 72's audit (an atom must reach
   the net's rows before its column can train). About half a day of code
   (one effect atom in the generator's grid with no training use, the
   burst's vocabulary widened to it), about 4 thread-h (one zero-shot read
   of one row, three bursts and their reads). Kill-fast: zero-shot cost
   under 2 HP on the row stops before any burst (nothing to cut); else
   the 33-game pooled cut under a third of the cost at 2 se says custom
   atoms need 62's description or more games.
   Held charter (not ready while one lane runs, `decision/one-lane`;
   ready again for the first exploration slot after `lane/final-round`): goal: goal 1's games-to-adapt on a custom mechanic built on
   an atom whose input column nothing trained; measure: one generated
   enemy row (an effect atom no official content, wide-pack mechanic or
   deck writes, chosen from registry::element_names() with 72's test,
   on an old trigger), the wide net s1 zero-shot @tsl1 one turn deep on
   1000 official elite starts x 4 seeds, then 33-game joint bursts from it
   (replay share 0.9, @tsl1, three seeds, the burst's vocabulary widened
   to the new column) read on the row and the parent, cut beyond parent
   against the zero-shot file (family.py gen_cut); stop: stop before any
   burst if the zero-shot cost is under 2 HP (nothing to cut); go if the
   pooled cut is half the cost or more at 2 se over nets with the parent
   within 1.5 HP; fail if under a third at 2 se (a fresh column needs
   more games or 62's description); kind: exploration; cap: 6 cpu-h;
   end: 2026-11-24; on-close: wake always.
74. **gbb-second-seed** (Source: navigator ideas run 2026-11-13, from
   `measurement/portfolio-genpack-burst-base`'s reopen condition; goal 1's
   games-to-adapt quote): the 11-game arm again from a second base-seed
   pair, generated-pack s101 (`runs/2026-11-11-genpack40k-s101-r1-065b3ff`)
   against pack-net-scratch s101 (`runs/2026-11-10-packnet40k-s101-r1-0559253`),
   the same two rows, recipe and pooled rule, plus gp101's zero-shot read
   on the two rows (pns101's is `gen-wide-pns101-tsl1.json`). Mechanism and
   value: the s1 go is between two particular nets; a second pair makes
   "a pool-trained base binds a trained column on a new pairing in 11
   games, the pool-less recipe gets worse" goal 1's quote rather than a
   lead. Trade-off: either base can win at s101 (gp101 paid more than gp1
   on the yardstick, +2.27 against +0.96). Rated **likely** (z 3.6 at s1,
   gp's worst burst seed above every pns net). No code (two family configs
   with the base swapped, a lane worker's copy), about 3 cpu-h. Ranks
   below 68 and 73 because the wide base, the one the project builds on,
   pays nothing on these rows: the quote describes the recipe's trunk,
   not a cost left to cut. Kill-fast: gp101 ahead of pns101 by 0.2 or
   more at 2 se replicates; within 0.1 says the s1 go was base-seed luck.

75. **level-defaults** (Source: owner discussion, 2026-11-13; goal 2's
   ruler and goal 1's reads; direction "Level and more general is a
   pass"; read 2026-11-13, decisions "Level-defaults read: `@tsl1` and
   `@lcb1` pass, `@hpe` one turn deep fails",
   `measurement/level-defaults@headline`): make the flags that tied, and
   are more correct or more general, the defaults, judged by
   `decision/level-pass`. No lane. (a) `@tsl1` in played fights, plain
   trial fights: **passed** (0966, +0.56 (0.19) HP, +0.016 clears, all of
   it on held-out sequences); the one-turn controls moved to its file and
   the `@tsl1` cell twin. (b) `@lcb1`: **passed** (0967 +0.15 (0.45) HP,
   +0.020 clears; 0969's yardstick rows within 0.05 HP). Both together
   (0972/0973, decisions "Combined one-turn control `@tsl1@lcb1` read"):
   **passed**, +0.76 (0.47) HP, clears 0.716 against 0.680 (+0.036,
   0.013), the parts' gains adding; `yardstick/one-turn-controls` moved
   to them. Two turns deep: 77. (c) `@tb1`: adopted
   (`decision/tb1-default`), waits for its code flip (probe sheet). (d)
   `@sn1` and `@xh1`: ride on the next from-scratch net that isn't a
   replication twin (Act 1's widened pool), read against its twin
   without. (e) `@hpe0.01` one turn deep: **failed** (0970, -1.74 (0.75)
   HP, -0.020 clears), the loss sitting in fights started near full HP
   (`cause/hpe-leaf-cap`); `@hpb` stays; reopens through 76.
   Kill-fast: any arm below the rule's bars stays off.

76. **hpe-leaf-cap** (Source: navigator ideas run 2026-11-13, from 0970's
   read, `cause/hpe-leaf-cap`; goal 2, the product's price, and 75(e)):
   `@hpe` prices every leaf at `min(HP + win heal, max HP)`
   (`py/src/lib.rs` `add_prices`), finished combats and fights still
   running alike. In a running fight the rest of its damage comes before
   the heal, so HP within the heal (6 for Ironclad) of max HP looks free
   and the search spends it. Fix: the cap and the heal only on finished
   combats (won states), linear HP (`HP - start HP`, scaled by
   `end_hp_scale`) at unfinished leaves; a new suffix so the product's
   string changes only on a pass. No double count (checked 2026-11-13):
   finished states never reach `add_prices`; the search prices them in
   `SearchConfig::finished` on HP that already holds the heal
   (`CombatState::won_healed`), so the fix touches unfinished leaves
   only, and at 80 max HP the fixed arm differs from `@hpb` only in
   pricing finished combats. **Mechanism evidence**: one
   turn deep `@hpe` and `@hpb` share the scale at 80 max HP and differ
   in the heal, the cap and finished-combat pricing; their play differs
   in 322 of 1,670 fights started at 74-80 HP and 26 of 538 below, and
   there `@hpe` loses +0.19 (0.05) HP per fight. **Trade-off**: the
   capped leaf gains where spending HP near full buys a faster win the
   net's value undercounts; the linear leaf gains the HP near full; both
   can win, the read decides. **Rediscovery**: the flaw of averages
   (Jensen): a concave payoff (the cap) priced at the current state, not
   at the expected final state; nothing in the record (`kb find win
   heal`, decisions "End-HP bonus built and read", which tuned `@hpe`
   two turns deep with the cap in place). **Rated likely** one turn deep
   (the fix removes the one place the two prices' play differs; against:
   finished-combat pricing could carry part of the loss), **even** for
   the product (two turns deep more lines finish inside the search, so
   the cap binds on fewer unfinished leaves; `@hpe` gained +0.036 clears
   over `@hpb` there with the cap in, `measurement/search-time-gains`).
   Under `decision/level-pass` a level product read passes (a misprice
   fix). **CPU**: about 2.4 thread-h one turn deep, about 7 thread-h for
   the product's headline read (`measurement/line-step@headline`'s wall
   time), 10 in all; code a few lines and a test. **Cheapest probe**
   (probe sheet, waits for code): the 10-29 net `@hpe0.01` with the fix
   one turn deep, plain leaf, on the headline at n 500 against the plain
   `@hpb0.01` file (the old one-turn control) and against 0970's file. Kill-fast: if it gains under 0.9 HP (half
   0970's loss) against 0970's file, stop (the cap isn't the loss); if
   it passes the level rule against the `@hpb0.01` file, 75(e) passes with it
   (the one-turn controls are then re-recorded with it, `@tsl1` and `@lcb1`)
   and the product read follows (the product with the fix, two turns,
   `--against` the headline control under `decision/level-pass`; pass:
   `scripts/product.py set`).


77. **product-level-flags** (Source: navigator ideas run 2026-11-13,
   from 0972's read and the reopened *tsl1-two-turn*: its reason, a gain
   too small to detect, no longer applies under `decision/level-pass`;
   goal 2, the product): the product with `@tsl1@lcb1` in played fights
   and `@hpe0.01@lcb1` trial fights (`--chooser`). Mechanism: both remove
   a misprice at the leaf, the turn-start hooks left out and leftover
   block priced with the wrong sign (`measurement/leaf-numbers@probe`);
   two turns deep the leaf sits after turn 2, where both misprices are
   still there, so the one-turn gains (+0.016 and +0.020 clears, adding
   to +0.036) shrink but keep their sign. Trade-off: the plain leaf gains
   only where the net learned to offset the misprice (it was trained on
   plain leaves); the fixed leaf gains wherever the misprice moved a
   line; both can win, and a tie passes. Rediscovery: the same flags,
   one turn deeper; *tsl1-two-turn* (2026-11-07) put the expected gain
   under 0.01 clears, which is why only a level read, not a gain, is
   asked. **Rated likely** to pass the level rule (each flag is exact by
   construction and level-or-better one turn deep on two settings),
   **a long shot** for a clears gain beyond 2 se (the product's seed
   sd and the two-turn search already playing Demon Form's first tick).
   Read 2026-11-13, job 0986: level under `decision/level-pass` (paired
   +0.08 (0.51) HP, lower bound -0.93 against -1; clears 0.832 against
   0.834). The pass moved the product string to `@hpe0.01@tsl1@lcb1`
   with the `@hpe0.01@lcb1` chooser, and the headline control to 0986's
   file (commit e24c419a; decisions "Product read 0986").

78. **final-run-inputs** (Source: navigator ideas run 2026-11-13, from
   the owner's 14 Nov plan (`decision/nov14`: a queue pause on 14 Nov,
   then the final training run) combined with the engine audit
   (`docs/research/engine-audit.md`, entries 1, 6, 9, 14) and 65's step
   0; goal 1 first (first-class custom content), goal 2 through the
   product's next base): a from-scratch net learns only from the inputs
   its encoding writes and the rules the engine plays, and a blind atom
   or a wrong rule fixed after the run costs another 40k learn (at least
   8 thread-h: 1002 reused its games and took 83 min at 6 threads; more
   with game generation). Mechanism: the run carries the cheap fixes the
   audit sizes S or S-M, in this order: (a) RoundEnd hooks as triggered
   rows (65's step 0, `cause/roundend-blind`); (b) the nine effect atoms
   with no column, after pins compare per named column (72, audit 9);
   (c) an exhaustive `Effect::scaled` (audit 6: 11 wide-pack copies'
   2-stack Dazed atoms add one Dazed); (d) shown_numbers and
   exhaust_hidden as net meta keys (audit 1, landed), so 75(d)'s twin
   can be trained; (e) the Act 1 content landed by then (colorless
   cards, relics). Rediscovery: a feature freeze before a release build;
   in this record `decision/headline-pool-after-act1` applies the same
   rule to rulers (controls built once, after the pool settles).
   Trade-off: waiting gains a base every later goal-1 read can trust on
   the fixed atoms; running at once gains the days (a)-(c) take (code,
   about a day of sessions), in which the CPU still runs
   65's seeds and reads. Rated **likely** as a sequencing rule (each fix
   is small and named; against: code is slow with one lane, and (b)'s pin
   rewrite is S-M). CPU: nothing beyond the run; it saves one 40k learn
   per fix that would come late. No probe (a list, not a choice);
   kill-fast: whatever of (a)-(c) hasn't landed by 2026-11-20 (65's end)
   stays out, and the run goes with what has. Lane order follows it:
   65's step 0 and 72's pin rewrite are the first code sessions after
   the restart. Not a decision yet: the owner's plan sets the run, and
   when it is queued the queueing role records which of (a)-(e) it holds.
   Since 2026-11-14 the run is at A20 (decisions "Ascension 20 becomes
   the default setting after the real-game day"): its readiness steps
   1-3 (an `ascension` key through learn, selfplay and finetune; the level
   in the registry; the choosers' 75 max HP) join this list as (f), and
   80 (a)'s A20 controls come before the run. Now a decision (owner,
   2026-11-14, decisions "The final training round, with the best setting
   reached so far", `decision/final-training-round`): queued by 2026-11-20
   with what has landed, recipe by seeds-go. Open as `lane/final-round`
   (2026-11-14), charter `docs/lanes/final-round.md`: (a) and 81's probe
   are its optional inputs 3(a) and 3(b); (b) and (c) wait for a second
   slot.

79. **view-at-a-pick** (Source: the real-game runs, 2026-11-14,
   `docs/research/real-game-runs.md` "Bugs the live runs found"; bridge
   commits 6336b37c, 0bb6f957; goal: the bridge's fidelity and its play
   inside random picks): `Combat.view()` / `Combat.from_view()` refuse a
   fight paused at a pick, so when the game asks for a pick the
   controller answers from one of the engine's 32 predicted samples, not
   from the game's state. Three live cases: Havoc+ playing a random top
   card that was Armaments (run 2; 6336b37c takes a sample that reached
   the pick); Warcry+ drawing two cards before putting one back (run 15;
   0bb6f957 prefers the sample whose piles are the game's); Distilled
   Chaos playing three random cards, one of them Armaments (run 22): no
   sample held the game's cards, the closest answered, one prediction
   miss (2720 of 2739 matched that day). Mechanism: let `from_view`
   rebuild a fight paused at a pick (the stage, the card in play and its
   next effect, the pick's kind and count) and `view()` write it, so the
   controller answers every pick from the game's own state; the sample
   search and its fallbacks then go. Rated **likely** to remove the case
   (the translator already reads every pile; against: the stage has
   several pick kinds, with the in-play card's remaining effects and
   InPlay flags, so it is S-M engine work plus round-trip tests). CPU:
   none. Cheapest probe: a round-trip test (`view` -> `from_view` ->
   `view`) on the three cases' picks from their recorded states; kill
   fast if a pick needs state the game doesn't show (then keep the
   sample search).

80. **a20-for-the-net** (Source: the real-game runs, 2026-11-14,
   `docs/research/real-game-runs.md` "Slime Boss at Ascension 20"; the
   owner asked for harder runs, and the engine plays every Act 1 monster at
   A20 since 725e8675; since the same day A20 is the default setting for
   training, decisions "Ascension 20 becomes the default setting after the
   real-game day", so (a) and (b) are the plan, not candidates; goal: the
   product at the game's hard setting): with
   packnet40k (trained on A0 fights), the A20 runs 28-36 beat Slime Boss 0
   of 3 times, Hexaghost 2 of 3 and The Guardian 1 of 1, and two more runs
   died before the boss (Lagavulin on floor 7; floor 12 at 10 HP, where the
   map then took a fight over a rest site). The engine is faithful at A20
   (99.6% of predicted steps matched, no miss from a monster's A20 rules),
   so the gap is the play. The Slime Boss read found no clear blunder (no
   turn ended with energy and a playable card left, no potion unused): the
   losses arrived with 49-64 HP, held 9-14 Slimed at once (3 at A0) and
   lost 18-33 HP in single monster turns. Candidates, cheapest first:
   (a) A20 as a gauntlet test setting (`gauntlet.py --ascension 20` puts it
   on every fight, trial fights included) for the product and its control,
   which sizes the A0-to-A20 gap in simulation; (b) A20 in training (fight
   specs take "ascension") or A20 trial fights for the chooser (the bridge
   already scores card picks at the run's level), for a net that prices
   A20 damage; (c) an HP-aware run layer (elites and rest sites by HP; the
   bridge's rest-below-half rule, 8d7d529a, and its map look-ahead to the
   next rest site, e28d1215, are first pieces), and gold: the bot walks
   past every shop, so gold is worth nothing to it, yet the event rule
   scores gold (Neow's 100 Gold over a card) and counts losing gold as a
   loss (World of Goop, Masked Bandits); dropping gold's score alone would
   make We Meet Again give a card instead of gold. Spend it at shops or
   price it at zero. Rated
   **even** for (b) moving A20 results (for: the net never saw A20 numbers;
   against: three losses is a small sample, and run-level HP may matter
   more than the fights). CPU: (a) one headline read at A20 (500
   sequences, the A0 read's cost); (b) a 40k learn. Cheapest probe: (a);
   kill-fast if the product's A20 boss clears on the headline sit within
   2 se of its A0 clears (then the gap is run-level, and (c) comes first).

81. **full-schedule-inputs** (Source: owner, 2026-11-14: "the net
   receiving the full enemy pattern as another input" and "look-ahead for
   partial states ... Act 1 bosses' and elites' move patterns"; the reopen
   condition of `pattern-rows-burst`; a design study the same day, three
   readers, three designs and a judge, workflow wf_63e1c2e9-894; goal 2
   through 78): inside the two-turn horizon the search already uses every
   certain fact. A move with one possible outcome is set at once with no
   chance event (`request_monster_move`, engine/src/chance.rs:188-194), a
   rolled move is searched over its exact odds, and a fully known next hand
   is one outcome. The gap is the leaf: the net sees each monster's HP,
   block, powers and the intent on show, nothing after it
   (`how/burst-inputs-monster`), so a threat past the horizon (Hexaghost's
   turn-9 Inferno, real-game run 48 at A20, lost from 67 HP with the boss
   at 100 of 264) is invisible. Deeper search doesn't fill it on this
   dev machine (`measurement/three-turn@elites` -0.75 (0.81),
   `measurement/rollout-leaf@elites` +0.67 (0.31) HP lost;
   `decision/depth-family-closed`). Earlier input forms showed only one or
   two moves, which the search already sees: lookahead columns +0.020
   against +0.045 on one-turn nets (decisions "Monster lookahead: no gain,
   stays off"), pattern rows Hexaghost +0.004 (0.002) one turn deep
   (`measurement/pattern-rows-burst@replay`). Content whose payoff lies
   past both horizons carries its one-turn gain whole to two turns
   (`cause/leaf-gain-past-horizon`, ratio 1.35 (0.50)). Mechanism: an
   opt-in row kind per monster, walked forward from `pattern_ai` over about
   8 rolls and cached per fight type like `RATE_TERMS`, with generic
   past-horizon columns: turns until the biggest hit, its expected damage,
   Strength gained before it, how certain the timing is, cycle length and
   place in the cycle. Plus `intent_pending` whenever `intent_known` is
   false (engine/src/agent.rs:58): `intent_damage` (agent.rs:51) reads the
   intent on show even while a rolled monster (A0 Nob, Jaw Worm, the M/L
   slimes, lice) or a monster behind it in slot order still has to roll,
   so the net sees the previous move there (the heuristic checks it,
   heuristic.rs:309). Generic, so custom monsters get it with no new code;
   moves the player triggers (Mode Shift, Lagavulin waking, Slime Boss's
   split; `lost_hp`, state.rs:5033) stay unseen. Rated **even** (for: the
   past-horizon columns show exactly what both searches miss, and the cause
   above says such gains survive depth; against: two near-zero partial
   reads, and a burst may be too small to train a new row kind). Code: S.
   CPU: the four boss bursts again with the rows, about 2.5-3.5 cpu-h,
   read two turns deep (a one-turn read undersells past-horizon gains) on
   the 474-fight boss replay against the same plain twins. Cheapest probe,
   near free: count two-turn leaves with `intent_known` false, and
   correlate scheduled-minus-averaged monster damage after the leaf with HP
   lost on Hexaghost replays; stop at about zero correlation. Fallback if
   the columns carry signal the net doesn't learn: a computed leaf
   correction (scheduled damage still to come minus the heuristic's
   averaged damage, priced 0.01 per HP), no training. Sequencing: before
   78's final run is queued; on a go the rows join 78's list. Kill-fast:
   Hexaghost under +0.008 pooled on the 1600-game pairs.

82. **leaf-beats-win** (Source: the real-game runs, 2026-11-14,
   `docs/research/real-game-runs.md` "Fight guard 1"; the bridge's fight
   guard covers it live; related to 76 `hpe-leaf-cap` but a different
   flaw; goal: the product's search at the game's hard setting): the
   search sometimes passes an immediate win. A finished win scores 2 - HP
   lost / 100 plus the @hpe term; an unfinished leaf scores the net's value
   plus the same term, and the net's value can exceed what any finish from
   that leaf can reach (more HP at the end than the HP now plus the win
   heal). Once a fight has cost a lot of HP, carrying on then beats
   winning: real-game run 56 (A20) left a Blue Slaver at 6 HP from turn 8
   to 18 (23 -> 5 HP; the kill scored 1.232, carrying on 1.27-1.34), and
   run 52 left a gremlin alive on floor 5 (turns 12-14, the fight cost 79
   -> 22 HP). Over the day's records 120 of 2983 decisions had a winning
   option not taken, most of them ties; the strict cases: run 56 floor 14
   (9 decisions), run 52 floor 5 (3), the A0 boss fights in record folders
   060511, 062806 and 080956 (wins at 1.569, 1.706 and 1.638 passed for
   1.581, 1.764 and 1.674), 062806 floor 6 and 145619 floor 7. Mechanism:
   cap an unfinished leaf's score at the best finish reachable at its HP,
   2 - (start HP - min(HP + win heal, max HP)) / 100 plus its @hpe term,
   so no leaf beats an immediate win at the same HP. Caveat: the cap must
   leave room for lines that really gain HP before the kill (Reaper,
   Feed's max HP, Regeneration, Bandage Up-like heals), or it undervalues
   them; one form caps at the HP the leaf's own healing can still add.
   Rated **likely** to remove the stalls (for: each recorded kill scored
   below carrying on at the same HP, which no finish can justify; against:
   the cap's room for healing lines is a judgment call) and **unknown** for
   headline numbers (a gauntlet stall ends later as a win or as
   "stalled"). Code: S (py/src/lib.rs `add_prices`, engine/src/search.rs
   `SearchConfig::finished`), a wheel build. CPU: one headline read if the
   probe shows a change. Cheapest probe: replay the 120 decisions
   (`results/real-game/*/decisions.jsonl`) with the cap applied and count
   the winning options the capped search takes; kill-fast if it changes
   none of the strict cases. Rediscovery: the optimizer's curse (Smith and
   Winkler 2006): an exact finished leaf against the maximum of many noisy
   unfinished ones loses to noise alone; the cap is an admissible bound,
   which removes the cases the bound can prove, not the noise. Taken into
   `lane/final-round` as its step 2 (owner, 2026-11-14, "prefer the
   kill"): a pass is read under `decision/level-pass` and joins the A20
   controls, the run's self-play and the product. 76 (the same function)
   stays on the probe sheet, apart, so the read stays clean.

83. **run-fight-cost** (Source: owner, 2026-11-14: "Should it share a part
   of the network with the player? Separate AI, or automated system?"; a
   design study the same day, three readers, three designs and a judge;
   goal: the run layer at A20, and goal 1 through effect-priced fights):
   the map prices every hallway fight at 15 HP and every elite at 40
   (`real_game_run.py:46`, pessimistic percentiles of runs 28-49), for any
   deck and HP, so a strong deck skips safe picks and a weak one walks into
   Lagavulin (runs 37, 49, 55). The judge's answer is a separate run layer
   that uses the fight AI as a tool, no shared weights (AscensionAI, the
   only shared-network StS agent, is the weakest outside result; the fight
   net stays the product). Mechanism: `fight_cost(deck, hp, encounter,
   ascension)` -> expected HP lost and P(death), from the net's start-state
   value (`value_offer_scores`, gauntlet.py:383-420) and, for close calls, 8
   A20 trial fights (`ladder.play_bench`), calibrated on the live record;
   it replaces FIGHT_COST/ELITE_COST in `map_command`. Rides along: gold
   scores zero unless a shop is reachable (80(c)); rest projection uses 75
   max HP at A20 (gauntlet.py:53). Rated **even** (for: HP spent on fights
   is where boss deaths come from, `cause/boss-deaths-elite-hp`, and trial
   fights price unseen monsters for free; against: an A0-trained net at
   A20, one-turn trials against two-turn live play, and three null
   run-level probes, `measurement/portfolio-run-decisions`). CPU: under
   0.5 cpu-h (the logged A20 Act 1 fights in `results/real-game/*/
   fights.jsonl`, decks from `states.jsonl`, 8 trial fights each at about
   0.07 s). Cheapest probe: cross-fitted prediction of HP lost per logged
   A20 Act 1 fight, against the per-room-type and per-encounter means;
   no live runs, no new content. Kill fast if it doesn't beat the
   per-room-type mean by 2 se in squared error (paired over fights): keep
   constants, re-set to the logged means. Next stage (not this entry): a
   replayed-real-map A20 ruler with paying elites, after act1-content's
   elite relics. Owner's order (2026-11-14): the run decision maker as a
   whole comes after run-level effects, gold, shops and events; this entry
   is the one piece that needs none of them. The same later stage values
   what a fight leaves for the rest of the run, as one item (owner,
   2026-11-14): gold, max HP, potions kept and relic counters. Today a
   fight's leaf prices none of them, so the live bot drinks potions
   greedily: in run 81 it drank a Blood Potion on The Guardian's turn 1 at
   73 of 78 HP, so 5 of its 15 HP counted. It also counts gold as nothing
   while it never shops, and Meal Ticket does nothing for it.

84. **best-first-search** (Source: owner, 2026-11-14: "early branch
   pruning ... begin exploration on more promising (evaluated higher) ones
   first", priority "best performance, then best run speed"; goal 2, the
   product's play, then its decision time): the search builds the whole
   tree first, then scores every leaf in one net batch and backs values up
   (engine/src/search.rs header). It expands options in `legal_actions`
   order (engine/src/state.rs:2329), so when a two-turn tree reaches the
   400k node cap (`max_nodes`, search.rs `expand`), the branches cut are
   whichever come last in hand order, not the least promising. The guarded
   player then falls back to one-turn's choice for the whole decision
   (decisions "Depth stays; guarded player before the engine fix"). Cuts
   hit 0-3% of two-turn searches on the headline's boss and train cells
   but 14-16% on held-out tight2 elite and boss fights
   (`measurement/cut-share@400k`). No pruning happens during play; only
   the exact solver bounds options (engine/src/bound.rs: an option whose
   best possible score can't beat the best solved one is skipped).
   Mechanism, in priority order: (a) performance: expand two-turn subtrees
   in the order of the one-turn search's option values (already computed,
   one batch), one batch per option, so the cap falls on the lowest-ranked
   options and a cut tree still decides among the top ones instead of
   falling back; optionally a per-option node share from its estimated
   size (the owner's "number of positions each action would take"); (b)
   speed: with values bounded in 0..2, prune with expectimax bounds (Star1,
   Ballard 1983: skip a chance node's remaining outcomes when even the best
   possible values can't lift it past the best option found), and stop an
   option once its upper bound (bound.rs's win-now bound, extended to
   leaves) can't beat the best. Real-game decision times today: median
   0.1-0.3 s, worst 46-111 s, mostly split-slime and louse boards
   (`docs/research/real-game-runs.md`, per-setting tables). Rated **even**
   for (a) (for: the cut cases are the hard fights where depth matters;
   against: on the headline cuts are rare, so clears move little), **likely**
   for (b)'s speed (bounded scores and a known win-now bound). Code: M
   (search.rs expansion order and per-option batches; Star1 at chance
   nodes). CPU: probe under 1 cpu-h. Cheapest probe: take the cut
   decisions from depth_paired's cut probe (`--probe-every`, held-out
   tight2 elite and boss fights) and re-search each (1) as today, (2)
   ordered by one-turn value at the same 400k cap, (3) uncut at a large
   cap as the reference; count how often (1) and (2) pick the reference's
   move, and time each. Kill-fast for (a): if (2) matches the reference no
   more often than (1)'s fallback by 2 se, drop it. For (b): if time per
   decision at identical choices falls by under 20% on the real-game worst
   boards, drop it. Not a depth change (`decision/depth-family-closed`
   stands): same depth, fewer wasted nodes.

85. **stalls** (Source: the real-game runs, 2026-11-14,
   `docs/research/real-game-runs.md` "The losses", run 83; related to 82
   `leaf-beats-win`; goal: the product's search at the game's hard
   setting): the search can loop without progress. Real-game run 83 (A20)
   fought four gremlins on floor 5 for 84 turns (60 -> 8 HP, then died to
   Lagavulin from 36): from turn 4 a Shield Gremlin at 4 HP gave a Mad
   Gremlin 11 block each monster turn, and each turn the two-turn search
   rated striking into that block (1.494) above the Strike that kills the
   Shield Gremlin (1.474), until turn 83 (`decisions.jsonl` floor 5, turns
   6, 20 and 40). It is play: the engine's Protect timing deviation
   (`how/act1-monsters-deviations`) did differ on turns 2-3 (it overrated
   Flame Barrier by about 4 HP there; a fix is in the Act 1 build plans)
   but not during the stall, turns 14-81. Within two turns
   killing the Shield Gremlin gains little, while the cost of leaving a
   protector alive (its ally re-blocked every turn) builds up past the
   horizon, and the net has no input for the Protect intent. The bridge's
   fight guard (82's stopgap) can't help: no single action wins the fight.
   Options: (a) the research fix, a Protect input for the net, or the
   general one, making progress visible at the leaf (a leaf where no
   monster lost HP or a defender over several turns scores no better than
   one that did), taken with 82; (b) a bridge stopgap, fight guard 2: a
   fight past a turn limit (about 30) goes to the fallback, which strikes
   the first living monster (a fighter change, so a setting version).
   Rated **likely** that (a)'s progress term breaks run 83's loop (for:
   the two options were 0.02 apart; against: a progress term may also
   rush fights where waiting pays). CPU: none for the probe. Cheapest
   probe: replay run 83's floor-5 decisions
   (`results/real-game/20261114-205554`) with a progress term at the leaf
   and see whether the search then kills the Shield Gremlin; kill-fast if
   it still strikes the block (then the net input is needed). Why two
   turns can't see it (navigator, 2026-11-14): the stall cost about 0.6 HP
   a turn (60 -> 8 over 84 turns), about 0.012 in score over the search's
   two turns, while the net preferred the stall leaf by 0.020: a loop that
   costs less per cycle than the net's error at the leaf survives any
   depth that sees only a cycle or two. So the fix has to price the cycle
   (the history form: monsters back in a state they held earlier in the
   fight's record, at lower player HP, score as the loop's limit) or
   remove the error (the Protect input); a leaf term needs a weight above
   0.02 to break run 83. Rediscovery: chess engines' repetition detection
   and fifty-move rule; RL's discount, which only helps if the value sees
   how long the fight has left, so a per-turn cost at the leaf doesn't
   separate two leaves at the same depth. Taken into `lane/final-round`
   as its step 2 (owner, 2026-11-14), with a check of how `learn.py`
   ends and labels a self-play game at the turn cap.

86. **chance-step-fidelity** (Source: the real-game runs, 2026-11-14, the
   Act 1 session's read of run 83; `docs/research/real-game-runs.md` "how
   fidelity is counted"; goal: the bridge's fidelity number covering every
   step): the controller compares the engine's prediction with the game's
   next state only when every sample agrees, so a step with chance in it
   (a draw, a random target, a rolled move, most monster turns) is never
   compared, and a difference there leaves no miss. Run 83, turns 2-3:
   Flame Barrier was up while a Shield Gremlin's Protect shielded the Mad
   Gremlin in slot 2; the game showed it at 21 HP with 7 block, the engine
   17 HP with 11 block, and the fight still counted 202 of 202 matched.
   Mechanism: once the game shows a chance step's outcome, condition on it:
   replay the engine from the previous view with the shown draws and rolls
   forced (or keep the samples whose draws, targets and moves match the
   game's) and compare the deterministic rest; report chance steps as their
   own count beside today's. Rated **likely** to surface monster-turn rule
   differences the count hides now (for: run 83's case; against: a sample
   that matches the shown outcome may not exist when hidden state differs,
   which is itself a finding). Code: S (scripts/real_game.py `predict` and
   `turn`, plus a replay script). CPU: none live; the states are logged, so
   the day's records (results/real-game/*/states.jsonl) can be replayed.
   Cheapest probe: replay run 83's floor 5 and count the chance steps whose
   matching sample disagrees with the game; kill-fast if no recorded fight
   shows one beyond run 83's.

87. **reward-precompute** (Source: owner, 2026-11-14: "We can't play
   many real games, if an optimization can save time on it, seems pretty
   sensible (if low priority) if it loses nothing"; goal: real-game
   throughput; **low priority**): the game rolls a card reward from its
   card RNG, which the run's seed and the saved counters fix before the
   fight starts (cards made in a fight use a separate RNG). So the bridge
   could predict the reward at fight start and run the sim chooser's
   trial fights while the game animates, then use the cached pick if the
   offered cards match. Today's picks: 856, median 0.7 s, mean 2.0 s, p90
   3.9 s, 28.8 min over all of the day's runs (about 30 s per run, ~5% of a
   run's time; `results/real-game/*/decisions.jsonl` "seconds").
   Mechanism: decode the autosave at fight start, as `save_seed` already
   does (scripts/real_game.py:1169; base64, XOR "key"), and read the card
   RNG's seed and counter. Replicate the game's reward roll: libGDX's
   RandomXS128 behind the game's counted Random; the rarity roll with the
   blizzard offset; the class pool order; duplicate re-rolls; the upgrade
   chance (lower at A12+); relics that change rewards. Precompute in idle
   time, never during a search. Rule: the prediction is a cache only.
   The fight's play must not read it, or the bot would use information a
   player doesn't have. Loses nothing: a mismatch just computes the pick
   as today. Rated **likely** to work (the RNG is deterministic; seed
   tools for the game do it), small gain. Code: M (the RNG and reward
   recipe must match the game exactly). CPU: none beyond the picks
   themselves, moved into idle time. Cheapest probe: log predicted vs
   actual rewards over a day of live runs without using the prediction.
   Kill-fast: under 90% exact matches, or no wall-time saving because
   the trial fights then compete with the fight search for the CPU.

**Checked and not proposed** (one line each; the reason stands unless new
evidence answers it):
- *elite-relic-reward* (2026-11-14, revival check of `cause/elite-does-not-pay`'s exit "elites pay a relic"): Act 1 relics load in combat, but `scripts/gauntlet.py` awards none, so the exit isn't met; giving elites a relic is run-level resource pricing, which the owner put in 83's later stage; reopen with 83's stage 2.
- *a20-burst* (2026-11-14, navigator ideas run: reach A20 by a fine-tune burst on the 10-29 net instead of a from-scratch round): A20 changes Act 1 monsters' numbers, not their mechanics, and bursts don't repair plain numbers (`cause/bursts-no-boss-or-stat`, `measurement/stat-burst@one-turn`), so the burst arm can gain nothing the round can't; reopen if a burst cuts a stat-only modifier's cost by half at 2 se.
- *best-of-three promotion* (2026-11-14, final-round's design): promoting whichever of three seeds reads best on the headline selects on the ruler (between-net MDE 0.06-0.07 clears at 500, `cause/headline-pairing-weak`); seed 201 is pre-registered instead and 1 and 101 only measure the spread; reopen if a confirm set (sequences 500-999) is read for every seed.
- *pack-exact-labels* (2026-11-13, from engine audit entry 12: give pack fights a codec encoding so the solver labels them, as exact labels for generated content): the solve step reads worth nothing on cells (`measurement/effects-vs-ids@cells`: lean minus the 10-29 recipe +0.001 clears, -0.22 HP) and `decision/solve-step-owner` keeps it unmeasured elsewhere; the encoding has other reasons (audit root cause 1), not this one; reopen if a lane shows the solve step helps on generated content.
- *level-sprt* (2026-11-13, after `decision/level-pass`: a non-inferiority SPRT, H0 -1 HP against H1 0, so level reads stop early, as Fishtest's simplification bounds do): at the headline's paired sd of about 10.7 HP per sequence (0.48 se at n 500) its expected stopping n under H1 is about 670, above the fixed 500, so it saves nothing; reopen if pairing cuts the per-sequence sd to about 7 HP (`cause/headline-pairing-weak`).
- *level-rule re-reads beyond the owner's four* (2026-11-13, decisions "Level-defaults reads queued"): `pattern-rows-burst` (cells -0.42 (0.19) HP against its twins, a cost beside the tie) and `burst-official` (a trained net, not a change of the rule's kind) stay closed; job 0333's flagged-trial arm met the bars but its closure rested on the chooser's overpick, so 0966 is the read.
- *wide-base-artifact-burst* (2026-11-13, after `measurement/gbb@g11`: the 11-game burst arm from the wide net s1): the wide net already pays +0.29 (0.24) HP beyond parent on GE-OppCard-Artifact zero-shot (gp1 +10.82, pns1 +9.92) and -0.55 to +0.67 on the other Artifact rows (`results/mutate/gen-wide-*-tsl1.json`), so a burst has nothing to cut; reopen on a wide-base row costing 2 HP or more that the wide pack's atoms cover (73 takes the uncovered case).
- *ritual-repair-source* (2026-11-12, after 0939-0941: which part of the 40k from-scratch recipe repairs Ritual 2 on elites, where the 10-29 net pays +1.68 HP): every later base is trained with that recipe, so knowing the part changes no choice; reopen if a base that drops part of the recipe (fewer games, no pack, another leaf in its labels) is proposed.
- *residual-rows* (2026-11-12, after 0906: a repair aimed at what every generated recipe leaves on the old held-out rows): split by parent it is OppCard-PlainDamage x Three Sentries (+1.2 to +2.9 HP after the 6-, 18- and 58-mechanic recipes, from pns1's +16) and a TurnEnd-Frail leak on Gremlin Nob and Lagavulin (+0.4 to +1.6, `docs/research/generated-enemies.md#Mechanic count (lane mechanic-count-curve; read by the navigator, jobs 0905, 0906)`), about 0.1-0.6 HP pooled: one cell and one known leak (`pack-retention`), below what a lane can show at its read floors; reopen if custom content with a punish-per-card power on a multi-monster encounter costs a recorded base 2 HP or more pooled, or the Frail leak passes 1.5 HP on an official parent in a lane's guard.
- *six-arm-seed-101* (2026-11-12, mechanic-count-curve's "between" step, offered after its go): a second 6-arm seed to confirm 0.88 (about 6 thread-h); the wide net's 0.98 on the same rows already says the count moves the held-out cut by about 0.1 from 6 to 58 mechanics, and no design waits on the difference; reopen as in `measurement/portfolio-mechanic-count-curve`.
- *player-genpack-scratch* (candidate 67 until 2026-11-12: a from-scratch learn with about 100-200 generated power cards in the deck pool, for the non-recurring generated player powers): its no-CPU probe killed it (`docs/research/genpack-yardstick.md#Candidate 67's no-CPU probe (navigator, 2026-11-12)`): on the 52 non-recurring generated cells every net (the 10-29 net, all-content twins, generated-pack nets, fslt bursts) is level with or ahead of the heuristic (-0.000 to +0.063 wins), so there is no measured cost to cut; reopen if a bench shows a net behind the heuristic on generated player powers by 0.03 wins at 2 se, or a generated character needs a base net.
- *wide-round-2* (2026-11-12, after `measurement/genpack-yardstick@18-seeds`: a self-play round on the wide net to recover its parent edge, 1.91 HP below the 10-29 net's r2 on official elites): `all-content-r2`'s reason stands (a round now trains for a card pool that changes with Act 1), and the gap to pns1, the same recipe without the pool, is 0.63 (0.26) HP, inside the -1.5 HP guards 65 reads; reopen if 65's cells or pack headline fall past -1.5 HP, or when the pool widens after Act 1.
- *genpack-product-net* (2026-11-11, after 0898: make the generated-pack net the product's fighter for its reach on custom content): `decision/crossed-player-lead` routes gains on new content to the product with the widened pool after Act 1, not by a swap on the curated ruler, where fighter swaps have read about +1 HP and no clears; `genpack-product-depth` reads the recipe two turns deep meanwhile; reopen when the headline pool widens or if that lane shows the generated-pack net lowering boss deaths two turns deep at 2 se.
- *card-two-turn-cost* (2026-11-11, card-later-ticks-burst's reopen check (a): the product two turns deep on `results/mutate/cards-a.json`'s starts, for the inflame-turn1 and metal-c2-a5 costs): the costs are small and pooled level over six power pairs @tsl1 (-0.006 (0.005) wins, `measurement/mutated-cards@stage-a`), two turns deep the search already plays the first tick, and new mechanics, not new cards, are what hurts (direction); reopen if a card family's pooled @tsl1 cost over its modifiers passes 2 se, or an Act 1 card whose payoff lands past the turn costs the net.
- *generated-card-space-scratch* (candidate 56 until 2026-11-11: a from-scratch learn with generated power cards in the pool, for later ticks on powers no game held): its probe answered it (`measurement/gen-powers@later-ticks`): nets that learned official powers' later ticks already carry them to unseen generated recurring powers and close the gap to the heuristic, so the learn has no measured cost to cut; reopen if a bench shows those nets still losing to the heuristic on recurring player powers.
- *specialist-teacher-burst* (candidate 50 until 2026-11-11: a burst whose games a from-scratch specialist plays, for later ticks): it opened only if `from-scratch-later-ticks` landed on start; it landed on count (`measurement/later-ticks-count@burst5k`), so the trained net learns them from its own games at a dose.
- *crossed-all-content-fighter* (2026-11-10, after pns-official: the 10-29 net picks, an all-content or pack net fights, to keep the Demon Form gain without the one-round picks loss): pns-twin-matched is that read, +1.15 (0.57) HP pooled, under the +1.5 bar, and two turns deep the product already plays Demon Form; reopen when the headline pool widens after Act 1.
- *all-content-r2* (2026-11-10: a second self-play round of the all-content net, as the 10-29 net had, to close its -1.50 HP outside Demon Form on the ruler): the owner's plan retrains on the widened pool once Act 1 is in and builds the controls once then (decisions "Headline card pool and choosers after Act 1"); a round now trains for a pool that will change; reopen when the pool widens.
- *per-cell-teacher* (candidate 31 until 2026-11-10: a pack burst whose games come from the teacher that plays each cell better, for the TurnEnd-Frail x Lagavulin leak): the leak is gone at g99 share 0.9 (-0.16 HP, `measurement/pack-dose-99s9@gen-b1`); reopen if a pack's shipped net loses 2 HP or more on a cell the gauntlet plays.
- *card-burst-dose* (2026-11-09, after `measurement/card-burst-share@stage-a`: inflame-turn1's burst at 99 games and share 0.9 to reach its plain-leaf bar): with the turn-start leaf no card burst of any size or share has closed any cost (-0.018 and -0.021 wins left), and the best plain-leaf burst (+0.024 at 400 games) only matches what @tsl1 gives with no games, so a bigger plain-leaf dose cannot gain over the leaf cards are read with; reopen if a burst closes a @tsl1 cost or a card's cost lands inside the turn.
- *source-removal-pairs* (owner discussion 2026-11-09, open question 16: train the net on interventional pairs, a position with and without a source, played out over the same 32 futures, beside its normal loss; a 5k-20k-position learning curve first, 3-10 cpu-h): on 4,448 pairs every fit tried (whole net, head only, a pull to the original weights, ridge on frozen layers; steps chosen on a validation split) stays at 0.21-0.33 held-out correlation against a reachable 0.81, and a quarter of the positions does as well as all of them (`measurement/pair-fit@recipe`); the labels are the student's own play-outs (`cause/teacher-equals-student`) and pairs are no new teacher, input or content under the training rule; reopen if an input change (candidate 44 or a state-aware card summary) lifts the fit past 0.4 on the same pairs, or a stronger teacher's play-outs are cheap.
- *ritual-share* (2026-11-09, `share-curve`'s reopen on a payoff past the horizon: Ritual 2 at 33 games share 0.9): 1602 games at share 0.5 cut only 0.38x of its cost, so the limit is what the labels hold past the one-turn horizon, not steps per game; a higher share on fewer games cannot gain there (`race-price` keeps the route).
- *own-boss-sim-chooser-now* (review 2026-11-09, direction 4: the sim chooser's trial fights against the sequence's own boss, on pack offers, about 1 cpu-h): run-level decision work before the content it chooses between (13 cards, every relic and potion missing; the direction's Avoid), and potions will change the boss fights; stays in `static-value-chooser`, which reopens with `act1-content`'s cards.
- *arrival-ruler* and *fresh-book-sprt* (review 2026-11-09, direction 1): the arrival score misses about a third of the two-turn edge (boss conversion +0.054 (0.018) of +0.154) and flips sign on one pair, as `boss-replay-score` was not adopted; fresh books are cheap only one turn deep and need controls on new ranges first (two turns deep 20-140 thread-h a read); a lane may add the arrival/conversion split as a descriptive column.
- *bench-joint-prices* (2026-11-08: tune `@esp` and `@shl` together on the whole bench, Texel-style, held-out mechanics as the check, about 6 thread-h): a value fitted on batch 1 needs the held-out read anyway, and 0566 is that read for the one price already near the front; reopen if 0566 goes and the headline read passes.
- *strength-delta-price* (2026-11-08, `measurement/portfolio-strength-by-hits-left`'s reopen (a): price only the Strength a choice adds over the root): a third hand-set price after `@esp` and `@shl`, the kind that trades (`cause/leaf-price-trades`), and the joint burst already halves Nob's cost with games; reopen if 0566 stops on a Nob row.
- *future-inputs* reopen check (2026-11-07): batch 1's costs exceed what their mechanics' means explain, but they sit on visible state (Nob's Enrage, the pack power on the monster), not on moves to come, so inputs for the future would not show them; stays withdrawn.
- *two-turn-gen-read* (2026-11-07: the product two turns deep on AttackLoss-Damage x Nob and OppCard-PlainDamage x Sentries, about 10 thread-h): moot; 0472 (the price) and 0473-0474 (a family burst) each remove both costs one turn deep.
- *drifted-lineages* (ideas#76, 2026-11-08: a curve of the net's lead over generations of stacked boon/bane modifiers): goal 1's cost follows the mechanic, not the distance in stats (`difficulty-shift` failed both steps), and stacks miss the sum of their parts by at most about 0.04 wins (`measurement/mutated-stacking@stage-a`), which the band guard holds down, so the curve is predicted flat; reopen when pack monsters carry two generated mechanics at once (then the lineage is the combination curve).
- *lcb-on-metallicize* (2026-11-07): `@lcb1` on metal-c2-a5, whose surplus block the leaf misprices; `@lcb1` left Impervious, the card with the most leftover block, where it was (-0.120 against -0.122 wins @tsl1, `measurement/leaf-clear-block@cells`), and metal-c2-a5's cost sits at bosses as a rate, not leftover block (`measurement/mutated-cards@stage-a`).
- *simulated-effect-inputs* (2026-11-07): describe content to the net by its measured effects; its probe fired: the six C1 new-atom cards and the two unreadable-trigger cards are level one turn deep (`measurement/act1-cards@zero-shot`), so blindness to an atom costs nothing where its effect lands inside the turn; reopen if content whose effect lands past the leaf costs and the net cannot read its atoms.
- *ids-effects-full-recipe* (owner's filler proposal, 2026-11-05:
  full-size ids twins of the effects nets): step 1 read it: ids are not
  ahead on the train half (five twins -1.24 HP) and their cost sits on
  the two unseen powers, where an id net sees `unknown`
  (`cause/unseen-cards-half-edge`); no size closes that.
- *demon-form-ban* (drop Demon Form from the product's offers) and
  *two-turn-trial-fights-for-powers* (the chooser's trial fights two
  turns deep where an offer holds such a card): at most about +0.01
  clears for the product (81 of 1000 sequences, 0.77 against 0.87);
  open question 11 counts eight more such powers in Act 1, so the second
  comes back when those cards are in the offer pool (run-level work,
  after the content).
- *two-turn-cells-by-card* (the product two turns deep on cell sequences
  250-499, about 8 cpu-h): two nets over 1250 sequences already put the
  two-turn leftover on Demon Form decks between nothing and a third.
- *burst-lottery* (train many burst seeds, keep the best on 0-499, confirm
  on 500-999): the best of 20 further draws is expected about 0.5 HP above
  the net in hand one turn deep, about 0.2 HP and no clears two turns
  deep (`decision/crossed-player-lead`); picking a lucky seed is not
  training with something new to learn.
- *crossed-confirm-read* (the crossed player two turns deep on sequences
  500-999, about 8 cpu-h): a pass swaps the fighter for about +1 HP and
  no clears, a fail changes nothing (`decision/crossed-player-lead`).
- *stageb-seed-twins* (more seeds of the SharpHide-then-stage-B burst):
  it would show a one-turn recipe on official play, which depth takes at
  the bosses; reopen if a one-turn net becomes a product of its own.
- *widened-product-net* (the product net fine-tuned with the 21 effect
  scalars it lacks, Burn's cost among them): the boss bursts were widened
  and gained nothing on Hexaghost (`how/burst-inputs`); what they lacked
  is the schedule (`pattern-rows-burst`).
- *burst-recipe* (rehearsing the parent fights in a burst): its reopen
  condition holds (burst8 loses 0.04 clears on train decks; every card
  burst loses parent HP at the elites), but its cheap form failed
  (`copy-rehearsal`, probe sheet: copy games raise the cost); reopen if
  a card burst repairs a @tsl1 cost or a pack's net is to play official
  decks.
- *value-chooser-confirm* (the value chooser on sequences 500-999, ten
  CPU minutes): no outcome changes what is built before Act 1's cards
  land (`decision/value-chooser-use`).
- *pack-enemies-from-official-parts* (the enemies bench on what stage 3
  loads today): familiar parts, predicted to cost nothing; the bench
  waits for generated powers on pack monsters (candidate 6).
- *coverage-curve-on-patches* (the k-families curve on today's patched
  powers, no code): the patches hold one family with a repairable cost
  (powers that punish attacking, which already transfer); the curve waits
  for packs (`generated-enemies-bench`).
- *data-curve-160k* (review 2026-11-06: a 160k-game pair if 80k reads
  above 40k): more games of the same kind is not something new to learn
  (the owner's training rule); the 80k read (jobs 0299-0300) only
  completes the record.
- *two-turn-transfer-read* (review 2026-11-06, direction 9: a 5k and a
  40k net two turns deep on 500 matched sequences, 15-40 thread-hours at
  2.5-4.4 GB): waits for the ledger's transfer table from pairs already
  on disk; it runs only if that leaves the ratio between 0.2 and 1.
- *hp-price-points* (review 2026-11-06: the leaf's HP price at 0.005,
  0.0075, 0.015 on the fresh control): every price so far moved under 1
  HP and a one-turn gain reaches the product at a third.
- *one-turn-screen-for-rungs*: under `decision/one-turn-comparisons` every
  rung reads one turn deep anyway.
- A burst as a product step on in-horizon mechanics: +1.1 HP on the
  mechanic against 0.60 HP on unchanged elites
  (`decision/burst-adapted-column`).
- *burst-net-on-bosses-two-turn*: +0.025 one turn deep is about +0.01 two
  turns deep against an se of 0.017-0.026 (`cause/leaf-gain-third`).
- *ensemble-on-unseen*: +0.007 / +0.009 on the unseen bosses, under a
  hundredth (`measurement/burst-bosses@replay`); on unseen-card decks the
  10-29 recipe's seeds and ensemble are level too (Metallicize decks
  +0.023 (0.009); decisions "After seed1-bosses").
- *games-to-adapt-two-turn*: neither read could change the adapted
  column's size of about 400 games.
- *two-turn-boss-games*: +0.02 clears needs about +0.18 one turn deep,
  where 1600 games gave +0.006 (`cause/teacher-equals-student`).
- *three-boss-retrain*: 1600 boss games level off at +0.02 to +0.03.
- *twin-own-picks-two-turn* (2026-11-10, after pns-two-turn-seeds: the all-content twins on the ruler on their own picks two turns deep): about +1 HP predicted (one turn deep +0.76 (0.87), their picks cost about 1.5 HP) against an own-pick floor of about 2.5 HP; the fighter question is 0846, matched.
- *three-turn-content-leaf* (2026-11-10, after pns-two-turn: three turns at the bosses with the pack net's leaf): 0819-0820 went, but at 1.35 (0.50)x the gain carries rather than grows, a plausible third-turn gain (+0.03-0.05 boss wins) is under even a 300-fight read's floor (about 0.06), and three turns peaked 8.2 GB (before `sparse-state`); `decision/depth-family-closed` stands; reopen if a past-horizon gain reads 2 se above 1x at two turns.
- *lookahead-on-unseen-bosses*: three twin pairs detect about 0.05 against
  an expected +0.02; open question 3's code read comes first.
- *three-turn-bosses-as-built*: 77 Hexaghost fights detect about 0.11
  (`hexaghost-headroom`).
- Two-turn search inside the sim chooser; three turns at the boss:
  `decision/depth-family-closed`.
- Training-recipe arms for goal 2: `decision/no-goal2-training-arms`.
- *heldout-settings*: expected difference about zero against a detectable
  0.07 clears (open question 6).
- *leaf-by-boss*: ~6 thread-h to gate a 1 thread-h probe; the one-turn
  Hexaghost lead is known (+0.069).
- The reactive-stack lead as its own lane: read in `adapted-two-turn`.

**Answered** (one line each; details in `docs/decisions.md`):
- *all-content-product* (candidate 48 until 2026-11-10, probe 0782-0783, `measurement/pack-net-twin@one-turn`): the all-content twins gain +0.76 (0.87) HP on the ruler one turn deep, all of it Demon Form, which two turns deep the product already plays; -1.50 (1.00) outside it; retired (decisions "Probe pns-twin-official read").
- *pack-dose-33* (candidate 38 until 2026-11-10, probes 0697-0701 and 0734-0738, `measurement/pack-dose-33@gen-b1`, `measurement/pack-dose-99s9@gen-b1`): 33 games each too few for eight mechanics; 99 at share 0.9 removes the Lagavulin leak and keeps the cut and the edge; pack chains train g99-sh9 (decisions "After pack-dose 99s9").
- *share-quote-widen* (candidate 46 until 2026-11-09, probe 0715-0728, `measurement/share-quote-widen@sentries`): 33 games at share 0.9 cut half or more on both damage-trigger mechanics; the trained parent spared on OppCard-Damage, +1.68 HP on OppCard-PlainDamage.
- *card-burst-share* (candidate 45 until 2026-11-09, probe 0702-0714, `measurement/card-burst-share@stage-a`): between; share 0.9 at 33 games spares the parents (metal-c2-a5's now gains) and keeps under half of inflame-turn1's plain-leaf gain; @tsl1 nothing closed.
- *second-character-census* (candidate 21 until 2026-11-07, a navigator subagent's code read, `docs/research/second-character-census.md`): of the Silent's 75 cards 47 are writable with today's vocabulary (20 already official), 5 more with the Ironclad's named blocks (69%), 23 need 13 new blocks, discard (D1-D3) holding 9 of them as exhaust did for the Ironclad; so the vocabulary converges, and a Silent pack waits on discard blocks, after Act 1.
- *experiment-ledger* (candidate 14 until 2026-11-07): built as `scripts/analysis/ledger.py` in `session-free-reads` (`measurement/ledger@cells`): no recipe since 10-29 beats it one turn deep, and none has a two-turn cell read.
- *coverage-pretrain* (candidate until 2026-11-07): folded into
  `generated-enemies-bench`'s coverage curve; its card evidence, burst8's
  Demon Form transfer, was the first tick (`measurement/burst8-tsl1@cells`).
- *fresh-range control* (open question 14): the product recipe's seed
  twins are level with the 10-29 net on sequences 1000-5999, so its lead
  on 0-499 was the book's draw (`measurement/fresh-control@cells`).
- *80k data point*: level with 40k inside the seed spread
  (`decision/no-goal2-training-arms`).
- *deck-matched-reads*: built; the read for fighting-only questions
  (`how/gauntlet-read`, `decision/matched-reads`).
- *matched-two-turn-adopt*: moot; comparisons play one turn deep
  (`decision/one-turn-comparisons`).
- *boss-replay-score*: not adopted (`measurement/boss-replay-score@one-turn`).
- *horizon-leaf-screen* and *novelty-gated-leaf* (the heuristic's choice
  where the state holds an untrained power): superseded by
  `turn-start-leaf`; the leaf sits before the trigger.
- *mutated-monsters-b*: built in `goal1-yardstick`.
- *rate features*: no repair on Ritual 2 (`measurement/rate-columns@ritual2`).
- *past-horizon-repair*: withdrawn (decisions "Stage A re-read").
- *rows-on-burst*: merged into `future-inputs`.
- *jitter-training*: shown wrong (`measurement/stat-burst@one-turn`).
- *full-inputs-retrain* (the product recipe again with today's inputs,
  pattern rows and the two unseen bosses): retired; its probe failed with
  validation loss inside the twins' noise
  (`measurement/portfolio-pattern-rows-burst`).
- *future-inputs*: withdrawn (decisions "After difficulty-shift"); reopen
  if generated enemies cost more than their mechanics explain.
- *pack-joint-burst* (2026-11-08, 0549-0553): one burst over a pack's mechanics keeps the neighbour edge single bursts lose; between on its rule (Nob cut 0.47, a Lagavulin leak); now `pack-adapt-pipeline`'s form.

## Parked

- **static-value-chooser** (with **own-boss-chooser** folded in): picks
  by the net's static values where every offered card is a trained card,
  by trial fights where one is not; the lead is +4 to +5 HP on
  train-card sequences (`decision/value-chooser-use`). Run-level decision
  work: reopen with `act1-content`'s cards and a net trained on them,
  confirming on sequences 500-999 first.
- **mini-run-headline** and **chooser-margin-rule** (the direction's
  "Avoid": run-level decision work waits for `act1-content`'s relics,
  potions and map): a second card offer doesn't pay an elite
  (`cause/elite-does-not-pay`); the mini-run stays a probe setting.
  Reopen with `act1-content`'s relics.
- **elite-payoff-relics** and **full-game-scope**'s content half: folded
  into `act1-content`; the run layer's decision-making stays parked after
  the content.
- **feasibility-ladder** (ideas#77): cells no longer rank nets, so it
  gains nothing on the current setting (trade-off rule).
- **outside-yardstick**: StS1 is now installed, and arena level 2 is the
  real game through the bridge (`decision/goal2-arena`,
  docs/specs/real-game-bridge.md), on the owner's machine time only; known
  bots stay open question 5.
- **line-through-chance** (ideas#80): only if line-step's cost (0.70)
  blocks its use; it doesn't.
- **solved-db-tooling** (ideas#72, ideas#61): only if the solver comes
  back into training (~70% of a non-lean round).
- ideas#70 (warm start from the curriculum's s1 r10 net), ideas#67 (held-out
  cards limit the gate), ideas#65 (gate checks ignore training luck),
  ideas#50 (rung 4 play-out averages), ideas#49 (two-turn relabel, with the
  outcome-label family, `cause/teacher-equals-student`): training without
  something new to learn doesn't get CPU (the owner's training rule);
  reopen only with a stronger teacher, new inputs (`future-inputs`) or new
  content.

