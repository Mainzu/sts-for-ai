# Outside yardsticks and run-level play (prior-art scan)

Started 2026-11-01 by manager f3fd4dee. Directions list: "an outside
yardstick (known StS bots ...); run-level play (card rewards, removal, rest
sites)". Goal 2 says "as dominant as Stockfish": dominance needs opponents
and a shared measure, and our measures are all internal (heuristic, ladder,
run-HP, now the Act-1 gauntlet).

## First principles

- Wanted: (a) a number that places our agent against other StS agents or
  human play (win rate per Act / full run at a given Ascension, or
  something translatable); (b) the designs that work for run-level choices
  (card rewards, removal, pathing, rest vs smith) on top of a combat agent.
- Inputs: a combat state (ours: Rust engine, Ironclad + Silent, Act-1
  monsters, no relics, no potions); a run state (deck, HP, gold, map) for (b).
- Outputs: a combat policy (have); a reward / map policy (don't have).
- Constraints: CPU only, one consumer machine (**hard**); the real game
  isn't installed, so no live play (**hard** until the owner installs it);
  no relics or potions in the engine (**soft**, subgoal adds them); headless
  simulator, no front end (**hard**, owner's scope note); measures must be
  paired and cheap enough to rerun per candidate (**soft**).

## Search plan

Angles, each one scout:

1. `sts-bots`: existing Slay the Spire bots and agents (CommunicationMod,
   bottled_ai, sts_lightspeed, MCTS / RL agents): reported win rates, at
   which Ascension, how measured.
2. `sts-academic`: academic papers and theses on Slay the Spire or
   roguelike deckbuilders (RL, search, card evaluation).
3. `draft-ai`: card draft / pick AI (Magic: the Gathering draft bots,
   Hearthstone Arena drafting, Legends of Code and Magic draft phase):
   valuing a card for a deck.
4. `dominion`: Dominion and other deckbuilding-game AIs (simulators,
   strategy optimisation, how buy decisions are learned).
5. `card-game-search`: Hearthstone / collectible card game AI competitions
   (MCTS with determinisation, evaluation functions), how they rank bots.
6. `variance-reduction`: measuring agent strength in high-variance games
   (AIVAT and DIVAT in poker, duplicate formats, control variates, paired
   seeds), outside the card-bot field.
7. `resource-horizon`: long-horizon planning where a resource carries
   across episodes (HP across fights; roguelikes such as NetHack, Brogue;
   multi-stage MDPs; "options" with a shared budget).
8. `game-ai-rating`: rating systems and benchmarks for game AIs outside
   chess (Elo / TrueSkill / Bradley-Terry in GVGAI, MicroRTS, general game
   playing), and how "dominant" is claimed.

## Search

8 angles, 8 paper scouts (Haiku), 67 sources opened (cards in
`sts-bots-and-runs/cards/`). Verified by the manager through full-text
fetches: SpireBench (arXiv 2610.12596, Table 1 and Sec. 4),
sts-ironclad-agent (README), AIVAT (arXiv 1612.06915, full text). Card
corrections: SpireBench's "top three win 90% of Act 1" holds for three of
the four (GPT-5.6 Sol is 70%); the 10 vs 15 seed conflict was two different
benchmarks (SpireBench 10 seeds, Epoch's SpireClimb 15 attempts), not an
error; sts-ironclad-agent's 501 games appear to exclude 6 bridge-faulted
seeds (implied, not stated). The other cards are scout summaries, unverified.

## What exists (verified)

| source | setting | headline | runs |
|---|---|---|---|
| SpireBench, Table 1 | real game, Ironclad A20, full run | mean acts cleared (0-4); Act-1 win rate | 10 seeds per cohort |
| - top LLMs (Fable 5.1, Astra, Opus 5) | | 1.30-1.60 acts; Act 1 90% | 10 each |
| - BottledAI (rule bot) | | 0.20 acts; Act 1 20% | 10 |
| - all humans (Mega Crit, 2020) | | 0.73 acts; Act 1 47% | 206,082 |
| - 1000+ hour players | | 0.92 acts; Act 1 54% | 8,287 |
| - streamers (Baalorlord etc.) | | 2.5-3.1 acts; Act 1 85-92%; Heart 46-65% | 46-687 |
| sts-ironclad-agent (README) | real game, Ironclad A20, Heart | 50.1% Heart wins, 95% CI 45.7-54.5 | 501 |

- sts-ironclad-agent (MIT) plays combat as search in a patched
  `sts_lightspeed` (gamerpuppy's MIT C++ simulator: all Ironclad cards,
  relics and enemies), and makes every out-of-combat choice (map, card
  rewards, shops, campfires, events, relics) with one network distilled
  from a hand-written teacher. Its stage death table puts Act 1 deaths at
  ~9% (Act 1 clear ~91%). Simulator-game parity is marked incomplete; its
  1,024-seed acceptance hasn't been run. It is the strongest reported StS1
  bot found, near streamer level.
- SpireBench, Sec. 4: at the Act-1 boss the top models hold a median 90%
  of max HP, the streamers 53%; models rest at 57-75% of rest sites,
  streamers 9%. Agreement with human card picks barely rises with model
  strength (rho 0.16). Strong players spend HP to build a deck; weaker
  ones hoard it.
- AIVAT: adding, at each chance event, (expected value over outcomes minus
  value of the outcome that happened) under any fixed value function is
  unbiased (Lemma 1, Theorem 1); a bad value function only weakens it. With
  chance terms only (MIVAT) the paper gets 18-34% lower SD (1.5-2.3x fewer
  games); the big gains (68-99.8%) come from also correcting the known
  players' own *random* choices, which a deterministic argmax agent like
  ours doesn't make.

## Fit table

| option | CPU only | no real game | headless | gain for us | size |
|---|---|---|---|---|---|
| A. Gauntlet clear rate as goal 2's metric (built today) | meets | meets | meets | internal number only | done |
| B. Price HP by the gauntlet: tune the `@hpb` constant for Act clears (shadow-price idea, as in RCPO or bisection on a multiplier) | meets | meets | meets | direct, cheap | a few jobs |
| C. Luck correction (MIVAT) on ladder / gauntlet | meets | meets | meets | ~1.5-2x fewer games at best; pairing already removes shared luck | engine must expose chance events and net values; medium |
| D. Use `sts_lightspeed` as the full-game simulator and yardstick | meets | meets | meets | outside-comparable runs (A20, relics, rewards) | large; a second engine |
| E. Real game through a mod bridge | meets | breaks (not installed) | - | the real yardstick | waits for the owner |

## Alternative framings (listed, not adopted)

1. **The outside yardstick is the sts-ironclad-agent setting, not our own
   engine.** Goal 2's "dominant" claim needs a number others report: Heart
   win rate at A20 Ironclad (best bot ~50%, streamers 46-65%). That needs
   relics, rewards, A20 and Acts 2-4, which our engine lacks;
   `sts_lightspeed` has them (MIT). Framing: keep our engine for goal 1
   (custom content), and build goal 2's run-level layer on, or checked
   against, `sts_lightspeed`. Loses: one engine for everything. Gains:
   years of fidelity work and a comparable number. Expensive to reverse,
   so it's the owner's call (it is also the rules-engine re-scope question
   from another side).
2. **Act clears, not HP per fight, set the HP price.** The bonus constant
   (0.01) was tuned on HP per fight at level wins. The run-level target is
   Act clears. Per SpireBench, strong humans reach the boss at 53% HP while
   models hoard 90%, so the right price may be lower than our per-fight
   one once rewards exist (and possibly higher in a fixed-deck gauntlet).
   Tune it on the gauntlet (option B). Cheap and reversible, so it's taken
   as the next experiment, not as a framing change.
3. **Cheaper measurement before more experiments.** Every comparison is
   CPU-bound; MIVAT at chance nodes could buy ~1.5-2x. Worth a pilot only
   once the engine exposes chance events; ranked below B.

## Recommendation

B now (it uses the gauntlet just built and needs no code): play the
champion on the gauntlet at c in {0, 0.005, 0.01, 0.02, 0.04} and read the
clear rate, paired by sequence. Then put framing 1 to the owner: it decides
what goal 2's headline number is and which simulator carries the full game.

## Checks borrowed from the literature

- SpireBench's scoring: acts cleared (0-4) and per-act win rates. The
  gauntlet's Act-1 clear rate has the same shape as its Act 1 column, but
  not the same level (ours is A0-like, fixed deck, no relics or rewards).
- sts-ironclad-agent's protocol: fixed fresh seed blocks, no reseeding or
  retries, a 95% interval on the headline. The gauntlet already uses fixed
  seeds and pairs by sequence.
- AIVAT's pilot check: compare the SD of the raw outcome with the SD of
  outcome + corrections before relying on it for a long run.

## Not applicable, and why

- LLM agents (SpireBench, SpireClimb, Orak): yardsticks only; far too slow
  for self-play, and they need the real game.
- MTG / Hearthstone draft models learned from human pick logs (Ward et
  al., 17lands): no human logs for our content, and SpireBench finds pick
  agreement barely tracks strength.
- Dominion / LoCM evolutionary deckbuilding with ~1M simulated games per
  run: a fit for card rewards later, once run-level play exists.
- Water values / SDDP (InFlow): grid dynamic programming, too heavy for our
  state; its idea (price a carried resource by its future value) is kept as
  option B.
