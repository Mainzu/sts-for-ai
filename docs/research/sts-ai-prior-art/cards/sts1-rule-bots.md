# StS1 rule-based and heuristic bots (CommunicationMod angle)

Scout: rule-based and heuristic StS1 bots, read through CommunicationMod or similar. Sources are GitHub repos, dev.to posts and docs, not papers. Venue is GitHub / blog; Cited by is GitHub stars where shown, else n/a. "Full text" for repos means the file was fetched through WebFetch and summarised; no raw source was run.

### bottled_ai README (2024)
- **Link:** https://github.com/xaved88/bottled_ai · **Venue:** GitHub · **Cited by:** 80 stars · **Read:** full text
- **Problem:** A customisable rule-based bot for Slay the Spire 1 that sees only what the player sees.
- **Method:** Enumerates ways to play the hand with graph traversal over a custom simulation, then picks the preferred outcome and plays cards in that order. Card, boss relic and upgrade picks follow prioritised lists per strategy (e.g. Watcher prefers Blasphemy over Tranquility). Some event choices are conditional (Shining Light: takes damage for two upgrades unless HP is low).
- **Assumes:** Its own StS1 game-state model, a hand-built simulator, and per-character strategy files. Non-ML; nothing learned. Priority lists name specific cards.
- **Claims:** The README says the bot "weighs about 40 values" when comparing outcomes. Best current Watcher result is 52% (see next card). No other numbers in the README.
- **Evaluation:** Live game via CommunicationMod; random seeds.
- **Code:** https://github.com/xaved88/bottled_ai, MIT license (per README).
- **Fit:** partial. Shows a whole-turn enumeration design that is a full-game rule bot, but the card-pick lists are per-card and do not generalise to unseen or generated cards, which our constraint requires.

### bottled_ai win rates (release-03, October 2024)
- **Link:** https://github.com/xaved88/bottled_ai/blob/main/docs/winrates.md · **Venue:** GitHub · **Cited by:** 80 stars (repo) · **Read:** full text
- **Problem:** Measured win rate of the rule bot per character.
- **Method:** Random seeds, the bot plays them; the authors aim for about 50 runs per character. Table of results: Ironclad RequestedStrike 20% (floor avg 32.7, 50 runs); Silent ShivsNGiggles 40% (38.5, 48 runs); Defect PwnderMyOrbs 33% (39.4, 52 runs); Watcher PeacefulPummeling 52% (45.86, 50 runs). Ascension level not stated.
- **Assumes:** Release-03 of the bot; the page's own note that the Ironclad 20% has a 95% CI of 8.9% to 31.1%.
- **Claims:** Authors say "This is not enough runs to attain high confidence!" and estimate about 1,000 games per character for ±3% precision.
- **Evaluation:** Random seeds, live game, one release, no stated Ascension.
- **Code:** as above.
- **Fit:** partial. The only reported strength number for an Ironclad rule bot (20%) is low and at unstated Ascension, so it is a weak baseline. The CI and sample-size note are useful for how we report our own win rates.

### bottled_ai capabilities page
- **Link:** https://github.com/xaved88/bottled_ai/blob/main/docs/capabilities.md · **Venue:** GitHub · **Cited by:** 80 stars (repo) · **Read:** full text
- **Problem:** Lists what the bot covers and its known gaps.
- **Method:** Not a method page. Shop handler covers cards and relics; potion purchasing is listed as future work. Combat path evaluation has a cap: "The bot will stop thinking after it has evaluated 11,000 battle paths".
- **Assumes:** Game state as CommunicationMod reports it.
- **Claims:** Known weaknesses listed by the author: missing cards for all four characters and many colourless cards; Silent poison needs "additional comparator adjustments"; the bot "doesn't know how to find the keys" (Heart); with many cards and enemies it "will often result in it just playing the card that's all the way on the right"; Prayer Wheel reward only checked if the first reward is taken; no potion handling (author proposes shared handlers); Writhing Mass intent changes and Time Eater healing not handled.
- **Evaluation:** Live game; no numbers.
- **Code:** as above, MIT.
- **Fit:** good as a list of failure modes. The author's own cap-then-fall-back-to-rightmost-card failure is the same kind of problem an exact expectimax with a node budget would hit, so it is worth designing against. Potions and events were unhandled, which our run layer must cover.

### spirecomm README (ForgottenArbiter)
- **Link:** https://github.com/ForgottenArbiter/spirecomm · **Venue:** GitHub · **Cited by:** 104 stars · **Read:** full text
- **Problem:** Python package for talking to the game via CommunicationMod, plus "a simple AI".
- **Method:** Coordinator dispatches in-game and out-of-game decisions to an agent; the example `SimpleAgent` is the rule bot.
- **Assumes:** Python 3.5+; kivy only for an example GUI; Communication Mod wired to run `main.py`.
- **Claims:** None. No performance numbers and no stated limitations in the README.
- **Evaluation:** Live game.
- **Code:** https://github.com/ForgottenArbiter/spirecomm, MIT.
- **Fit:** partial. It is the interface layer, not a strength claim. Useful only as a reference protocol adapter.

### spirecomm example agent: combat, reward, map, shop, rest (SimpleAgent)
- **Link:** https://github.com/ForgottenArbiter/spirecomm/blob/master/spirecomm/ai/agent.py (also `main.py`, `spirecomm/ai/priorities.py`) · **Venue:** GitHub · **Cited by:** 104 stars (repo) · **Read:** full text
- **Problem:** A hand-written rule policy for every decision in a StS1 run.
- **Method:** Combat: pick zero-cost non-attacks first, then nonzero-cost cards, then zero-cost attacks; defensive mode when block > incoming damage minus (act + 4); AoE override; attacks target lowest-HP monster. Potions used only in boss rooms. Card reward: `get_best_card` returns lowest rank in `CARD_PRIORITIES` minus 0.5 per upgrade; `should_skip` is true for cards ranked below `"Skip"`; `MAX_COPIES` caps copies. Map: a DP over `MAP_NODE_PRIORITIES` per act, e.g. Act 1 (Ironclad/Silent) `{'R': 1000, 'E': 10, '$': 100, '?': 100, 'M': 1, 'T': 0}`. Shop: purge, then first card with `should_skip` false, then first relic. Rest: rest if HP < 50%, or on floor % 17 == 15 with HP < 90%; then smith, lift, dig; then rest if HP < max.
- **Assumes:** Ironclad/Silent/Defect data tables in `priorities.py`; one rule per decision, no search.
- **Claims:** None stated. The rest rule `floor % 17 == 15` is unexplained in the code.
- **Evaluation:** Live game; no numbers in the repo.
- **Code:** https://github.com/ForgottenArbiter/spirecomm, MIT.
- **Fit:** partial. Concrete reference for the fixed run-layer rules we currently have. Its card priorities are per-card names, so they break on unseen or generated content; the map priority values are a useful baseline for the fixed map rules.

### Doron Singer, "Part 11: pick your battles" (dev.to, Silent)
- **Link:** https://dev.to/doronsinger/part-11-pick-your-battles-d3p · **Venue:** blog (dev.to) · **Cited by:** n/a · **Read:** full text (summary via WebFetch)
- **Problem:** Whether a search-based combat planner beats a rule bot on Silent fights.
- **Method:** Looks ahead, then rolls out a fixed opening strategy with search. Scores end-of-search states with a learned heuristic trained on combat outcomes. A cleaned-up label set moved best-plan match from 26% to 46% (random 35%).
- **Assumes:** Silent; a simulator that can clone and roll back states; budget not stated. Labels had a bug (full potion belt valued at about 3 HP) that was fixed.
- **Claims:** Benchmark of 147 fights from 150 games: hallway 63 fights, 0 losses, 4.0 avg HP lost; elite 84 fights, 19 losses, 28.9 avg HP lost; all 147, 19 losses, 18.2 avg HP lost. Later production agent lost 3 of 84 elite fights; 96% win rate and 9.4 avg HP lost for the unrestricted agent. Stated limits: long fights degrade, missing enemy intents past Act 1, a foresight bug (agent sees future draws) that was left in and "Averaging over multiple possible futures failed."
- **Evaluation:** Silent fights, 150 games; hallway and elite splits.
- **Code:** none found.
- **Fit:** partial. The rollout-plus-learned-evaluator design is close to ours, but it is Silent, and the author's future-draw leak and failed averaging are direct warnings for any chance-averaging design.

### Doron Singer, "Part 3: good models finish last" (dev.to, Silent A20)
- **Link:** https://dev.to/doronsinger/part-3-good-models-finish-last-2n6a · **Venue:** blog (dev.to) · **Cited by:** n/a · **Read:** full text (summary via WebFetch)
- **Problem:** Card-pick prediction from human data, and whether better offline accuracy means better play.
- **Method:** Logistic regression over a 113-card count vector (called a "tier list"), then a model with relic and game-state features plus a state encoder and card encoder (~202,000 parameters), trained to predict human picks.
- **Assumes:** Silent, Ascension 20; human-played data (34,210 runs, 358,870 pick decisions).
- **Claims:** Own runs 334 at 41% win rate. Model offline accuracy 53.5% on human picks. In-game on 50 seeds vs the spirecomm expert: embeddings+mechanical features 55.8% offline, beat/lost/tied 12/23/15, 4th; mechanical features only 53.5% offline, 16/16/18, 1st; embeddings+propensity 52.3%, 15/22/13, 3rd; propensity only 49.5%, 14/21/15, 2nd. Conclusion: better offline pick prediction did not translate in-game; the simplest model did best.
- **Evaluation:** 50 seeds per variant, expert = spirecomm.
- **Code:** none found.
- **Fit:** good for the card-pick question. It is direct evidence that imitation accuracy does not predict in-game strength, relevant to any learned pick policy. Silent only, and the 50-seed sample is small.

### Doron Singer, "Part 6: what not to consider" (dev.to, Silent)
- **Link:** https://dev.to/doronsinger/part-6-what-not-to-consider-54g5 · **Venue:** blog (dev.to) · **Cited by:** n/a · **Read:** full text (summary via WebFetch)
- **Problem:** Which search and evaluator ideas failed for a Silent planner.
- **Method:** AlphaStS base with clone/rollback. Search: look ahead until the budget, take a no-HP-loss win if found, otherwise best heuristic and re-evaluate next turn. Heuristic: win +1000, reward HP, poison, debuffs; penalises Nob's strength and early Lagavulin wake; block scaled 1.5x; assumes 12 damage per turn. Dominance pruning removes strictly inferior states, cutting 90-94% of candidates for about 10x speedup.
- **Assumes:** Silent, simulator set to Ascension 20 while the headless game ran easier; budgets 5s hallway / 20s boss.
- **Claims:** Table: expert BFS (bottled_ai) avg floor 34.0, 26% wins, 11,000-state cap. Pre-fix search 18.4 avg floor, 0% wins, 10,000-state cap. Post-fix 19.3, 0%, 500 ms/decision. Dominance-pruned search 28.7, 2/30 (6.7%), 5s/20s. Learned MLP evaluator (638→256→128→1, 89K samples from 30 games) 27.2 vs handcrafted 28.8 at 5s/20s, 30 games. Author: a 512-state cap "re-introduced the exploration problem"; bigger budget gave 24.0 avg floor, 0% wins.
- **Evaluation:** Silent, 30 games at 5s/20s; expert BFS baseline from bottled_ai.
- **Code:** none found.
- **Fit:** good. Gives the only measured comparison with bottled_ai's search (26% wins, floor 34.0) and the 90-94% pruning figure, which bears directly on the node-budget and state-cap design. The baseline's Ascension and game count are not stated.

### CommunicationMod (ForgottenArbiter)
- **Link:** https://github.com/ForgottenArbiter/CommunicationMod · **Venue:** GitHub · **Cited by:** 156 stars · **Read:** full text
- **Problem:** Lets an external process drive StS1 through stdin/stdout.
- **Method:** Sends JSON game state when it is stable; accepts commands START, POTION, PLAY, END, CHOOSE, PROCEED, RETURN, KEY, CLICK, WAIT, STATE; replies with new state or an error.
- **Assumes:** Slay the Spire, ModTheSpire and BaseMod; a hand-edited SpireConfig command; live game only.
- **Claims:** None quantitative. Stated limits: full Match and Keep state not sent; potion use with a full inventory gives no feedback; hand-select unselect unsupported; some manual actions do not change state; not tested with fast mode off.
- **Evaluation:** Live game.
- **Code:** https://github.com/ForgottenArbiter/CommunicationMod, MIT.
- **Fit:** partial. Only relevant if we want a live-game bridge for validating our engine against the real game. Live play is slow and the protocol is not a simulator.

## Not opened (for the verify step)
- AscensionAI technical writeup (justinochan.github.io, PDF): listed in search results, not opened.
- benmuth/AutoClad (supervised learning, not rule-based): listed, not opened.
- Doron Singer parts 4 and 9: listed in search results, not opened.
- A 2026 CommunicationMod-based StS2 bot series (tomokinotes.pages.dev) targets Slay the Spire 2, not StS1; not opened.
- No Reddit or forum write-up on StS1 combat turn permutation or win rates was found in the search; not opened.
