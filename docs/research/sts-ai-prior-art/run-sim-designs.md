# Run simulator: four designs and three judges (raw)

Written 2026-11-15 by a design workflow (four designers, each given one approach, then three judges: goal fit, cost and code, risk), for `docs/research/sts-ai-prior-art.md` "Run simulator: options". Designers read the repo and the jar but edited nothing; sizes and costs are their estimates. The synthesis and the checks done by hand are in the report; this file is the raw material for the spec.

## A. Run layer as registry content (Rust)

**Run layer as registry content: one Rust run machine, three chance backends, data events.** Everything outside a fight becomes registry content (run effects, conditions, events as small screen machines, reward/shop/Neow tables) run by one steppable Rust `RunState` machine. Each random procedure is written once against a chance trait with three backends: the jar's own RNG (seed-exact replay of the real-game logs), xoshiro (fast sampling) and the existing enumerator (exact averages where outcomes are few). Fights stay outside the machine and are batched as today.

### Architecture

Alternatives weighed. (a) Porting lightspeed's GameContext.cpp (114 KB, events inline): rejected at the owner's request, and it fails goal 1 because each event is code. Its tree search also reads the game's RNG, which breaks need 4. (b) A run layer in Python, growing out of gauntlet.run(): CPU is no reason against it (the run layer is under 0.1% of a run's cost either way), but it would split content between two loaders, and Rust search or planning could not call it. (c) Only the real game through CommunicationMod: about 30 runs a day, three orders of magnitude too few. (d) Chosen: data-first in the engine. The Rust machine is small and generic, and the content is JSON in the same registry as cards and monsters.

Components (new Rust under engine/src/run/, estimates):
1. engine/src/run/gamerng.rs. The jar's Random (com/megacrit/cardcrawl/random/Random: a libGDX RandomXS128 plus a counter; random(int)=nextInt(range+1), random(a,b), random() as a float, randomBoolean, randomLong, the counter-restoring constructor) and java.util.Random's LCG, which the game uses for Collections.shuffle(list, new java.util.Random(rng.randomLong())). Streams kept: the run-level ones (monsterRng, mapRng = seed+act, eventRng, merchantRng, cardRng, treasureRng, relicRng, potionRng) plus the per-floor miscRng = seed+floor (AbstractDungeon.java lines 386-419 and 1859).
2. engine/src/run/chance.rs. A trait `RunChance` that extends rng.rs's `Chance` with the game's call shapes: int(range), range(a,b), float_lt(p as f32), boolean, shuffle(list), each tagged with its stream (Card, Relic, Event, Misc, ...). Three implementations: `GameStreams` (gamerng, seed-exact), `Fast` (one xoshiro Rng per stream, split from the run seed) and `Exact` (rng.rs `enumerate()`, extended with an arity cap: a site with at most K outcomes is enumerated and a larger one is sampled, so a result is a weighted list that is exact on the small sites).
3. engine/src/run/state.rs. `RunState` holds only what the player sees: act, floor, hp, max_hp, gold, deck (CardIds plus upgrades), relics with counters, potions, the map with symbols (? rooms stay '?'), the current node, the event pools still unseen (the game's eventList, shrineList and specialOneTimeEventList contents, which a player can infer), the ramp numbers (EventHelper ELITE/MONSTER/SHOP/TREASURE_CHANCE, card rarity offset, potion drop chance), the boss name (shown on the map) and `screen: Screen`. Like the combat engine (engine/src/state.rs), it holds no RNG. Anything the game rolled in advance and hides lives in a separate `Hidden` struct next to the chance backend: the act's pre-rolled monster/elite lists (monsterRng at act start) and the relic pools' shuffled order (relicRng at run start). The planner never gets Hidden: it gets `Hidden::resample(&RunState, chance)`, which redraws it consistent with what was seen (e.g. the encounter-list no-repeat rules, relics not yet seen).
4. engine/src/run/step.rs. One step machine: `pending(&RunState) -> Pending` with Pending = Decision{kind, options: Vec<Opt>} | Fight{encounter, group, deck, hp, relics, potions, reward_spec} | Done{won}. `choose(&mut RunState, &mut Hidden, &mut dyn RunChance, opt)` and `fight_result(&mut RunState, won, hp_end, relic_counters, potions_left)`. Screens: Neow, Map, Room entry (the ? roll via EventHelper.roll at entry, as the game does), Event{id, screen}, CombatReward{items}, CardReward{cards}, Rest{options}, Shop{stock}, Chest, BossRelic, Grid{purpose} (upgrade/remove/transform picks). A fight is never played inside the machine: the caller collects Pending::Fight from many runs and plays them in one batched call, as gauntlet.run() does today with `play(specs)`.
5. engine/src/run/map.rs. MapGenerator (343 lines decompiled), RoomTypeAssigner and AbstractDungeon.generateMap/generateRoomTypes (lines 513-600), rewritten in Rust from the decompiled jar and checked seed-exact. This is the one place the jar's algorithm is transcribed rather than described as data, because the map is an algorithm, not a list of items.
6. Registry: registry.rs gains a `run` section in pack files, parsed next to cards/monsters/relics, with entries interned like the others and their words in content/wording.json (engine/tests/wording.rs catches a miss). Python: py/src/lib.rs gains `sts.Run(seed, ascension, character, chance="game"|"fast")` with .pending(), .choose(i), .fight_result(...), .obs() (a dict in the same shape the bridge builds), and `sts.run_outcomes(obs, option, cap)` for planners: weighted successors from a resampled Hidden and fresh chance, never the live streams.

### Content model

A run effect vocabulary (Rust enum `RunEffect`, parsed in registry.rs like `parse_effect`): GainGold(a), LoseGold(a), Heal(a), LoseHp(a), GainMaxHp(a), LoseMaxHp(a), ObtainCard{card|pool roll}, RemoveCards{n, pick|random, of: types}, UpgradeCards{n, pick|random, of}, TransformCards{n, pick|random}, DuplicateCard{pick}, ObtainRelic{name|tier roll, screenless}, ObtainPotion{name|roll}, LosePotion, Fight{encounter, reward}, OpenReward{gold, cards, relic, potion}, Goto{screen}, Leave, SetFlag/Counter, Random{stream, outcomes:[{p, effects}]}, Chance{stream, p, then, else}. Amounts reuse effects.rs's `Amount` shape (base + k/per × quantity) over a new `RunQuantity` (MaxHp, Hp, Gold, DeckCount(type), Floor, Ascension, Counter), so "heal a third of max HP" is {"Heal": {"of": "MaxHp", "k": "1/3"}}, parsed by registry.rs's existing `amount()`/`fraction()` code. Conditions (`RunCond`): GoldAtLeast, HpAbove, HasRelic, HasCardOfType, DeckHas(tag), Ascension≥n, Act, Flag. They gate options (the game's disabled options), effects and pool eligibility.

An event is a small screen machine. Example Big Fish (events/exordium/BigFish.java): {"id":"Big Fish","pool":"event","acts":[1],"screens":{"intro":{"options":[{"label":"banana","effects":[{"Heal":{"of":"MaxHp","k":"1/3"}}]},{"label":"donut","effects":[{"GainMaxHp":5}]},{"label":"box","effects":[{"ObtainCard":"Regret"},{"ObtainRelic":{"tier":"Random","screenless":true}}]}]}}}. Ascension variants reuse registry.rs's `patch()` (today used for monster levels) as "at": {"15": {...}}. Golden Idol is two screens plus a trap screen. Scrap Ooze and Dead Adventurer use a Counter with an escalating Chance. A probability names its game stream ("misc", "event", ...), so the GameStreams backend makes the same calls in the same order as the jar.

Engine-owned primitives, a closed set like PickKind, for the few mechanics that are not a list of outcomes: MatchPairs (Match and Keep), CardOfRarityOffered (Bonfire Elementals' outcome by the offered card's rarity), NoteForYourself (a fixed card here, since cross-run memory is out of scope). These are referenced by name from data.

Tables are data too. content/run/acts.json: per act the event, shrine and one-time lists (Exordium.java lines 211-230, AbstractDungeon line 1438+), boss list, encounter pool names (encounters.json already exists) and the elite floor rule. content/run/rewards.json: card rarity odds per room kind, gold ranges, potion drop rules, relic tier odds (returnRandomRelicTier). content/run/shop.json: slot layout (5 colour cards by type, 2 colourless, 3 relics with the shop-tier rule, 3 potions, removal), price ranges, sale tag, the ascension price factor. content/run/neow.json: the four option groups and their drawbacks (NeowReward.java, 431 lines) as effect lists. A relic's run part is a `run` key on its existing pack entry (content/packs/act1-relics.json), with hooks keyed by run triggers: OnPickup, RoomEnter(kind), RestOptions, RestEnter, CardRewardSize, CardAdded, FightWon, ShopEnter, PriceFactor, ChestOpen, GoldGained (the modifier for Ectoplasm). This is the vocabulary docs/specs/run-layer-relics.md step 3 proposes, moved into the Rust registry instead of a Python-loaded content/run-relics.json.

A new custom or generated element needs only a pack entry (an event with screens, a relic with run hooks, a Neow option, a shop slot rule) plus its words in wording.json. It loads through `load_pack` like official content and is eligible through the same pools. scripts/gen_content.py can emit events and relics in the same schema.

### Fidelity plan

Three tiers, all run by programs.
(1) A differential oracle on the real jar. The game's JRE ships jjs.exe (Nashorn) and IntelliJ's jbr has javac, so a script can call the jar's own rendering-free classes directly: Random, RandomXS128, java.util.Random shuffles, MapGenerator.generateDungeon, RoomTypeAssigner, EventHelper.roll, probably the card/relic/potion roll helpers. A Rust test compares each of these call for call against GameStreams over about 10k seeds (estimate). The game's CPU is never involved. Whether classes that touch AbstractDungeon.player or the UI can be stubbed headless is unknown; if not, they use tiers 2 and 3.
(2) Replaying the real-game logs. results/real-game/*/states.jsonl carries seed, map (with symbols), act_boss, deck, relics, gold, potions and every screen's options (Neow, events by event_id, card rewards, combat rewards, rest, chest, grid). A harness (scripts/run_parity.py, Python) runs `sts.Run(seed, chance="game")` through each logged run, feeding the logged choices and the logged fight results (hp after a fight, potions used) as inputs. At each screen it asserts that the generated screen equals the logged one: map and symbols, boss, Neow's options, each ? roll's room type and event id, event options, card reward cards, gold amount, potion drop, relic, shop stock. 70 logged runs times about 15 run screens is about 1000 checks (estimate), growing by about 30 runs a day.
Seed-exact parts: map, boss, the act's encounter lists, Neow, ? room types and events, event outcomes (miscRng is reseeded from seed+floor at each floor), card, gold, relic and potion rolls, and shop stock. These hold as long as the combat engine's fights do not consume those streams in the real game (see risks). Not seed-exact: the fights themselves (the engine uses xoshiro), which the replay takes from the logs.
(3) A test per item. Each event, relic run hook, Neow option and table row gets a Rust test generated with it. The test enumerates the item's outcome distribution from a fixed RunState with the Exact backend and compares it to an expectation written independently from the decompiled class, by a second reader. Where the item appears in the logs, tier 2 covers it too. A coverage report (extending docs/research/act1-coverage.json) lists each item's tiers and how often it appears in the logs.

### Chance and hidden information

Exposure. Each random procedure (a card reward, an event's coin flip, a ? roll, a shop roll) is one function over `&mut dyn RunChance`. With `Exact`, `sts.run_outcomes` returns every outcome with its probability where each chance site has at most K outcomes (K about 8, tunable by measurement). Examples: an event's Random/Chance, a ? room's type, a card reward's three rarity rolls (27 combos), gold amounts. Larger sites, such as which card of a rarity or which relic from the pool, are sampled, and their result carries weight 1 inside the exact frame. This is docs/direction.md "exact before sampling" at the run level, reusing rng.rs's `enumerate`.

Hiding. RunState holds only what the player sees, and it has no RNG, as in the combat engine. Unvisited ? rooms hold only '?', because the game itself rolls them on entry. Future rewards do not exist until rolled. The two pre-rolled hidden things (the act's encounter lists and the relic pool order) live in `Hidden`, which only the authoritative simulator uses. A planner or learner gets only `obs()` plus `run_outcomes`, which draw from a resampled Hidden and a fresh chance source, never the live GameStreams or the true Hidden. A test asserts that two runs with equal obs and different seeds give identical `run_outcomes` (the leak check). Ramp numbers (elite chance, rarity offset, potion chance) are in the observation: a careful player can compute them from what they saw.

### Shared with the bridge

Both paths share one decision shape. CommunicationMod screens are converted into the same Pending::Decision dict that `sts.Run.obs()/pending()` produce (scripts/real_game_run.py gains `decision_of(gs)`, about 200 lines). The run choosers (today's map_command, event_command, reward_command, rest_command and boss_relic_command rules, and later a learned chooser) then take that dict in both the simulator and the real game. One chooser implementation runs in both, and RUN_RULES-versioned rules become a chooser named in a setting.

They also share the content and the rolls. The bridge can construct `sts.Run(seed, chance="game")` alongside the live game and advance it with the same choices. That gives a live parity check every bridge run (a mismatch is logged as a fidelity bug), and lets the bridge's chooser call `run_outcomes` for lookahead over the real run, since the live game's hidden state is never read. Fights stay shared already (the same engine and nets).

### CPU cost

Estimates. Rust run layer per Act 1 run: map generation tens of µs, about 60-100 decisions and rolls at a few µs each. Under 1 ms per run, against about 6-17 thread-s of fights one turn deep (12-17 fights at 0.5-1 s) or about 150-200 thread-s two turns deep. That makes the run layer under 0.01% of a run's cost, and about 3,000-9,000 one-turn runs an hour on the dev machine, bounded entirely by fights. The run layer's speed matters only for lookahead planners that call `run_outcomes` many times per decision. Those must price fights with the value net (gauntlet.py's net_values/value_parts path, milliseconds each), not with played fights, or the planner multiplies the fight cost. Memory: a RunState is a few hundred bytes, so thousands of runs held at once for batched fights fit easily.

### Code estimate

Estimates. Rust: about 3,000 lines of new code (gamerng 250, chance backends 250, run state and step machine 1,000, map 600, rewards/shop/Neow logic 500, registry parsing of run content 400) plus about 1,500 lines of tests. Data JSON: about 26 Act 1 events at about 25 lines each (about 650), Neow about 80, shop about 60, rewards about 60, acts about 60, relic run hooks about 45 rows. Python: run_parity.py about 300, bridge decision_of and chooser refactor about 300, gauntlet driver over sts.Run about 300 (replacing part of run()). Oracle JS about 100. For comparison, lightspeed's out-of-combat C++ is about 147 KB (GameContext, Map, Shop, Neow), roughly 4,000 lines.

### Cheapest probe

About 1-2 hours, scratchpad only, no repo edits. Write a jjs (Nashorn) script run with the game's own jre/bin/jjs.exe and desktop-1.0.jar on the classpath that builds `new com.megacrit.cardcrawl.random.Random(seed + 1)` and calls MapGenerator.generateDungeon(15, 7, 6, rng) for the seed of 5 logged runs. Compare the node and edge layout with gs['map'] from their states.jsonl. A match proves headless jar calls work and the map can be seed-exact, which is the foundation for both the oracle tier and the log replay. If RoomTypeAssigner also runs headless, compare the symbols too.

### Build steps

| Step | Size | Check |
|---|---|---|
| GameStreams: the jar's Random/RandomXS128 and java.util.Random shuffles in engine/src/run/gamerng.rs, plus a jjs oracle script in scripts/oracle/ (scratch output under results/, cleaned by its --clean flag) | S (about 250 Rust, 80 JS; estimate) | a Rust test runs 10k seeds × 1000 mixed calls, byte-identical with the oracle's dump |
| Run effect/condition vocabulary and relic run hooks in registry.rs (the `run` key on pack entries), wording entries; delivered as docs/specs/run-layer-relics.md R2's vocabulary (R2 builds on it rather than a Python loader) | M | engine/tests/wording.rs; one test per relic hook (expected max HP / gold / deck after OnPickup etc.) against the relic class |
| RunState + step machine + `sts.Run` binding; gauntlet.run() re-expressed as a driver over sts.Run on today's fixed SHAPE (no map yet) | M | old gauntlet files replay byte-identical on the same seeds with the run features off (the R2 spec's pinned-sequence test) |
| Reward rolls (card rarity and offset, gold, potion drop, relic tier and pools) seed-exact, plus scripts/run_parity.py log replay up to the first unmodelled screen | M | all logged card rewards, gold and relic rewards in the 70 runs match; a mismatch report lists the first diverging screen per run |
| Map (MapGenerator, RoomTypeAssigner), ? roll (EventHelper.roll), act encounter lists and boss, rest site, chest, boss relic | M (about 600 Rust) | oracle on 10k seeds; every logged map, act_boss and encounter sequence matches |
| Neow from content/run/neow.json | S | logged Neow options match in all runs; per-option effect tests |
| Shop from content/run/shop.json (stock, prices, sale, removal cost) | M | logged shop screens match; price-range tests against ShopScreen/StoreRelic/StorePotion |
| Events: an automated per-event workflow (decompile the class, write JSON, a second reader writes the expected distribution, generate the test); Act 1's 11 events + 6 shrines + about 9 eligible one-time events | L in count, S each (about 26 items; estimate) | per-event Exact-distribution test; every logged event screen matches; coverage report |
| Bridge: decision_of(gs) in real_game_run.py, the rules as a chooser over the shared shape, and a live shadow sts.Run with mismatch logging | M | the bridge's choices are unchanged on replayed logs (same command per screen); shadow mismatches are 0 on the modelled screens |
| Only then (backlog 83, direction.md Avoid): the run decision maker trained or tuned on simulated runs | out of scope | its own spec |

### Improves on sts_lightspeed

- Content is data in the shared registry (events, Neow, shop and reward tables, relic run hooks), not C++ inline in a 114 KB GameContext.cpp, so custom and generated elements load like official ones (goal 1)
- One procedure, three chance backends: seed-exact game RNG for parity, fast xoshiro for volume, exact enumeration with an arity cap for planning. lightspeed only replays the RNG
- Honest information by construction: RunState holds no RNG, pre-rolled hidden lists sit in a separate Hidden that planners only see resampled, and a leak test checks it. lightspeed's tree search knows the game's RNG state
- Differential tests against the real jar through its own JRE (jjs/Nashorn) over thousands of seeds, plus replay of the bridge's real-game logs, instead of hand comparison
- Fights are external and batched across many runs, matching the threaded combat engine and gauntlet's play(specs) batching
- One decision shape and one chooser shared with the real-game bridge, and the bridge can shadow every live run with the simulator
- Every element is worded from wording.json, so the explorer can show run content as it shows combat content
- Built to be extracted per item by Claude Code workflows, with a generated test per item

### Borrows

- sts_lightspeed: the list of run-level RNG streams and the order they are used in, as a cross-check lead only, with the jar deciding
- Decompiled jar: MapGenerator/RoomTypeAssigner/generateMap, EventHelper.roll and the ramp chances, RewardItem, ShopScreen/StoreRelic/StorePotion, NeowEvent/NeowReward, Exordium's event and shrine lists, AbstractDungeon's stream seeding (seed, seed+floor)
- This repo: rng.rs's Chance trait and enumerate(); effects.rs's Amount and registry.rs's amount()/fraction()/patch() parsers; load_pack and wording.json; gauntlet.py's batched play(specs) and chooser kinds; real_game_run.py's rules as the first chooser
- silverbot / sts-ironclad-agent (prior-art survey): their run layers were learned on full-run simulators, which is why a simulator comes before the decision maker

### Risks

- The real game's combat may consume run-level streams that the engine's fights don't (potionRng for in-combat potion creation such as Entropic Brew or White Beast Statue; cardRng from some card generators). Then rewards after such a fight are not seed-exact in replay. Mitigation: the parity harness names the first diverging screen; replay can resync a stream counter from logged rewards; the simulator is unaffected (it is its own ground truth)
- The jjs oracle may not load classes whose static initialisers touch libGDX graphics or AbstractDungeon.player (likely for events and shops). Then those items rely on log replay and the second-reader tests only
- Rare events seldom appear in the 70 logs (about 2 per event so far), so their parity rests on the reading tests until more bridge runs accumulate
- A few mechanics don't fit outcome lists (Match and Keep, Bonfire's rarity outcome, We Meet Again's random loss). Engine-owned primitives keep them data-referenced, but each is code to keep in step
- Enumeration can grow: chained Random effects multiply outcomes. The arity cap needs a total-branch cap too, tuned by measurement
- Scope clash with the R2 draft (docs/specs/run-layer-relics.md plans a Python content/run-relics.json). If R2 builds in Python first, the vocabulary exists twice. The manager should fold R2's step 3 into build step 2 here
- The Hidden resampler must reproduce the game's encounter-list rules exactly, or planners see a slightly wrong distribution of future fights

## B. The jar as oracle, Rust run layer as data

**Jar as oracle, Rust run layer as data: a game-exact run simulator checked against the game's own code.** The installed jar runs headless as a test-vector generator and a replay referee. The simulator's run layer is a new data-driven Rust module (engine/src/run/) with a port of the game's RNG. Every run procedure is written once against a chance interface, so the same code can replay a seed exactly, average exactly or sample. The bridge and the simulator share one observation type and one decide() function.

### Architecture

VERDICT ON THE JAR: use it as the test-vector generator and the log-replay referee, not as the run layer at sim time. I checked the dependencies with a constant-pool scan of desktop-1.0.jar plus IntelliJ's decompiler. There is no javap in either JRE folder; JBR has javac.
- com/megacrit/cardcrawl/map/MapGenerator uses no LibGDX at all, only MapRoomNode, MapEdge, Random and ModHelper. MapRoomNode's constructor uses only the cosmetic MathUtils.random (jitter).
- com/megacrit/cardcrawl/random/Random wraps gdx RandomXS128 with a counter.
- events/exordium/BigFish uses no LibGDX, but its constructor goes through AbstractImageEvent -> AbstractEvent, which calls ImageMaster.loadImage. Its static block needs CardCrawlGame.languagePack (LocalizedStrings, which reads localization/eng/*.json via Gson). Its effects go through AbstractDungeon.player, effectList (ShowCardAndObtainEffect) and getCurrRoom().spawnRelicAndObtain.
- AbstractDungeon's static initializer builds TopPanel, CardRewardScreen, ShopScreen, DungeonMapScreen and others, so touching any run code pulls in UI construction.
- AbstractCard's constructor calls cardAtlas.findRegion. The TextureAtlas is built from Gdx.files and will NPE if it is null. ImageMaster.loadImage catches exceptions and returns null.
- The jar itself ships gdx-backend-headless 1.9.5 (HeadlessApplication, MockGraphics, MockAudio) and the natives gdx64.dll and gdx-freetype64.dll.
So the feasible harness is: HeadlessApplication, then Gdx.gl = Gdx.gl20 = a java.lang.reflect.Proxy no-op GL20, so Texture, TextureAtlas and FreeType fonts 'load' against a fake GPU. Fall back to shadow stub classes ahead of the jar on the classpath, compiled with JBR javac --release 8, if a constructor still fails. Prior art shows the game logic runs without rendering: sts-ironclad-agent ran the stock jar under ModTheSpire with SpireLabLogic's fixed logic frames and read 13 dungeon RNGs plus shared sources, though its oracle missed NeowEvent.rng. Doron Singer spent weeks aligning a headless game.

Why not at sim time:
(a) All game state is static singletons (AbstractDungeon.*), so one JVM holds one run. The chooser's lookahead (gauntlet.sim_choose / sim_fights score each option by playing fights from its afterstate) would need replay-from-seed per branch.
(b) The jar can only roll. It cannot list an event's or a reward's outcomes with their probabilities (docs/direction.md, exact before sampling).
(c) Goal 1: custom or generated run content would have to be Java classes, or a second interpreter in Java for our data. Official content would then not load the same way as custom content.
(d) It holds every hidden value in one heap next to the agent.
CPU does not decide the question: the run layer costs well under 1% of a run either way.

COMPONENTS:
1. tools/jar-oracle/ (Java 8 source, compiled locally with JBR javac against the user's installed jar; the jar and decompiled source are never committed). A long-lived JVM driven by JSON lines on stdin/stdout:
   - init(seed, ascension, character): Settings.seed, ascensionLevel, all unlocks forced, CardLibrary/RelicLibrary/PotionHelper init, new Exordium(player, ...)
   - map(): nodes, edges, room symbols
   - neow(): the 4 NeowReward options
   - card_reward(room), shop(), chest(), boss_relics(), event_roll() (EventHelper.roll plus generateEvent)
   - event(id, state, option): sets player HP/maxHP/gold/deck/relics, constructs the event, calls buttonEffect(i) by reflection, ticks effectList with a fake delta, returns the state delta
   - rng_counters(): the 13 AbstractDungeon streams plus NeowEvent.rng
   Every reply includes how many calls each stream consumed.
2. engine/src/run/ (Rust, new):
   - rng.rs: GameRng, a port of Random/RandomXS128 with the murmur seed hash and counter; JavaRandom, the 48-bit LCG for Collections.shuffle(list, new java.util.Random(rng.randomLong())) as used in initializeRelicList; and RunRng, the 13 streams plus neow, kept outside the state the way engine/src/state.rs keeps combat RNG outside.
   - map.rs: the game's map algorithm. This is the one deliberate piece of code; its numbers live in data.
   - state.rs: RunState is what the player sees: floor, act, HP/maxHP, gold, deck, relics with counters, potions, map and position, boss, screen.
   - interp.rs: the run vocabulary interpreter.
   - rewards.rs, shop.rs, neow.rs: thin; their tables are data.
   - obs.rs: RunObs plus the option list.
3. registry.rs gains the run content kinds, parsed like the combat packs. New atoms go in registry::element_names() with words in content/wording.json; engine/tests/wording.rs catches misses.
4. py/src/lib.rs: sts.RunSim(seed, settings, packs) with obs(), options(), step(i) -> next screen | Fight(spec) | End, apply_fight(result), outcomes(i) for planning, and replay(choices).
5. Python: scripts/run_layer.py holds decide(obs) (today's RUN_RULES rules moved out of real_game_run.py, later the learned one) and observe(gs) -> RunObs from CommunicationMod fields. gauntlet.run() gets a run-sim mode in which play(specs) still plays fights in the Rust engine.

CHOICES are 'apply these rows' candidates (docs/extending.md, a choice is a decision between changes), and the agent picks among afterstates (concept.md). CHANCE is a Roll atom in data that declares both its game form (stream, call kind, range) and its cases.

### Content model

Everything is data in content/run/*.json or a pack, loaded the same way for official, custom and generated content (decision/registry-first).

- EVENT (content/run/events.json, or a pack such as content/packs/gen-events-*.json): {id, acts, pool: event|shrine|one_time, eligible: [conditions such as GoldAtLeast 35, HpAbove, FloorAtLeast, HasRelic], screens: {intro: {options: [{label, when: [conditions], rows: [run atoms], next: screen|leave|{Fight: {encounter, rewards}}}]}}}. Roll atoms carry the jar's consumption: {Roll: {stream: misc, call: {int: 99}, cases: [[0, 49, rows], [50, 99, rows]]}}.
  Example, BigFish: Banana = Heal {of_max: 1/3}; Donut = GainMaxHp 5; Box = [AddCard Regret, ObtainRelic {random: {tier_roll: relic}, screenless: true}].
- RUN ATOMS: a closed list that grows by appending. It starts from the R2 draft's list in docs/specs/run-layer-relics.md: GainMaxHp, HealFull, Heal, GainGold, UpgradeRandom, Transform, RemoveCards, DuplicateCard, RewardSize, UpgradeAdded, ExtraReward, RestOption, NoGold, NoPotions, NoRest, NoSmith. Added to it: LoseHp, LoseMaxHp, LoseGold, AddCard {id|random{pool, rarity, type}}, ObtainRelic {id|random{tier}}, ObtainPotion, PickCard {from: deck|offer, filter, then: rows}, CardReward {room}, Fight, OpenShop, Leave.
- RELIC run side: the `run` key on the relic's entry in content/packs/act1-relics.json, with trigger plus rows, as the R2 draft proposes. Triggers: OnPickup, RoomEnter, RestOptions, CardReward, CardAdded, FightWon, ShopPrices, ChestOpen.
- NEOW: content/run/neow.json, four categories of NeowRewardDef-like rows, each with optional drawback rows and the NeowEvent.rng roll forms.
- SHOP: content/run/shop.json. Slot layout (2 attacks, 2 skills, 1 power, 2 colorless, 3 relics with the last from the shop tier, 3 potions), base prices per rarity, the 0.9-1.1 and 0.95-1.05 merchantRng jitters, the sale slot (merchantRng.random(0, 4)), removal cost and its step, and A-level modifiers.
- REWARD TABLES: content/run/rewards.json. Card rarity odds per room type, with the rare offset that grows on each common (cardBlizz), potion drop chance with its +/-10 step, gold ranges per room, relic tier odds, chest kinds.
- MAP: content/run/map.json. Grid size, path count, room-type shares, row rules (first row hallway, row 9 treasure, row 15 rest, no elite or rest before row 6), A1+ elite multiplier.

A NEW CUSTOM ELEMENT needs: rows only, if it uses existing atoms (tier A in extending.md). A new atom (tier B) needs one interpreter arm in interp.rs, an element_names() entry, wording, a test, and an oracle vector when there is a jar original. A generated event is a pack file that the same loader reads, worded by the explorer from wording.json.

### Fidelity plan

Three checks, all programs:
(1) ORACLE VECTORS: tools/jar-oracle writes engine/tests/data/run-vectors/*.jsonl, and engine/tests/run_parity.rs replays them. The vectors are:
   - RNG: per call kind, 10k sequences, including setCounter.
   - Maps: 10k seeds, Act 1, room types included.
   - Neow options and card rewards: per seed and room sequence, with the rareChance offset carried.
   - Relic pool order after initializeRelicList's five shuffles.
   - Potion drops, gold, chest contents, shop stock and prices, ? room outcomes (EventHelper.roll on eventRng plus generateEvent), and the boss relic offer.
   - Per event: (state, option, stream position) -> state delta plus calls consumed per stream.
   Each extracted item gets its own vector file and test, which is where Claude Code automation pays off. A workflow per item decompiles the class, writes the data row, asks the oracle for vectors over a spread of states (low gold, full HP, has relic X), and runs the test until it passes.
(2) LOG REPLAY: scripts/tests/test_run_replay.py walks results/real-game/*/states.jsonl (70 runs now, about 30 a day). It takes the seed (logged on every state) and the logged choices, drives RunSim.replay, and compares the offered options at each MAP, EVENT (Neow included), CARD_REWARD, COMBAT_REWARD, SHOP, CHEST and boss-relic screen with the logged screen_state. Fights take the logged outcomes. It reports the first divergent screen per run.
(3) DISTRIBUTION CHECKS: for the few paths that are not seed-determined even in the game. AbstractDungeon.transformCard(c, autoUpgrade) defaults to new Random(). returnColorlessCard() shuffles with the global Collections RNG. The oracle samples those over seeds and a chi-square test compares them with our enumerate().

What can be seed-exact: everything on the run streams: map (mapRng), encounter lists (monsterRng), Neow, card/potion/gold/relic rewards, relic pools, ? rooms, event choice and outcomes (eventRng, miscRng, which resets to seed+floor on each room as nextRoomTransition shows), shop (merchantRng), chests (treasureRng), boss relics.
At risk: any place a fight consumes a run stream, for example potionRng or cardRng touched in combat by our engine's relics or potions. Our combat engine would have to report those calls. The replay check exposes these.
The scan found cosmetic-only MathUtils.random in MapRoomNode, ShopScreen, NeowEvent and Merchant, and the game-relevant shuffles seeded from miscRng (DeadAdventurer, ShiningLight, GremlinMatchGame).

### Chance and hidden information

One procedure, three drivers. Every run procedure (reward roll, ? room roll, event option, Neow, shop stock) is written against a RunChance trait that extends engine/src/rng.rs's Chance. Each call says its stream and its game call form: random(int), random(float a, b), randomBoolean(p), randomLong-seeded shuffle.
- GameRng (the port) drives it seed-exactly, for replay, parity and plain sampling (it is also the fast sampler).
- rng::enumerate drives it for the exact distribution, whenever the outcomes are few: a card reward's rarity roll, an event's coin flip or 50/50, the ? room type (4 outcomes), which event out of about 15-25 eligible, Neow's category draws.
- Sampling with a fresh xoshiro Rng (never the game stream) covers the rest, for example the identities of 3 cards within their rarities (about 10^4-10^5 combinations). Rarity stays exact and identity is sampled, and the spec says why.

HIDDEN INFORMATION: RunRng lives outside RunState, the way the combat engine keeps its RNG out of state.rs. RunObs is built from RunState only, and the afterstate key used for dedup is RunState. Things are rolled when the player would see them, matching the game's own order: a ? room's type and event at entry (the game rolls EventHelper.roll on an eventRng duplicate at room entry), a card reward at the reward screen, shop stock at entry, chests at opening, boss relics at the boss chest. Things the game shows up front are visible: the whole map and the act boss.
The planning API RunSim.outcomes(i) enumerates or samples from the public state with its own Rng and never reads RunRng, so a planner cannot learn the true future. The jar oracle never runs alongside an agent: it is only used offline for tests and replay.

### Shared with the bridge

Shared: the RunObs type with its option list, the decide(obs) function, the content data and the vocabulary interpreter.
- In the simulator, RunSim emits RunObs.
- In the real game, scripts/run_layer.py observe(gs) builds the same RunObs from CommunicationMod's game_state and screen_state. Field meanings come from GameStateConverter, as real_game.py already uses them.
decide(obs) returns an option index, and a small adapter turns that into the CommunicationMod command, keeping real_game_run.py's map_command, event_command, reward_command, rest_command and boss_relic_command as adapters only. The fixed rules (RUN_RULES 5, MAP_RANK, GOOD_WORDS/BAD_WORDS, FIGHT_COST/ELITE_COST) move into decide() as the first decision maker, so the bridge and the simulator measure the same chooser.
The bridge can also compute RunObs-side facts from data instead of from words. For example, an event option's rows tell the agent 'Box: Regret plus a random relic' instead of word-scoring 'lose' or 'curse'. That fixes the run-52 Golden Idol class of error.
The log-replay test is the contract that the simulator and the bridge mean the same thing at every screen.

### CPU cost

Estimates. Rust run layer per simulated Act 1 run, with about 50-100 decisions, one 7x15 map and about 20 reward or shop rolls: roughly 0.1-1 ms of one thread. Fights cost 12-17 x (0.5-12 s), about 10-200 thread-seconds, so the run layer is under 0.01% of the run. Enumerating outcomes for planning costs microseconds.
What matters for CPU is how many fights the decision maker plays per option (today's sim_choose plays fights per offer). Three things keep that down: afterstate dedup (equal RunState, one value), value-net leaves (gauntlet.value_choose), and exact enumeration of the few outcomes instead of many sampled seeds.
The jar oracle, offline only: JVM start plus library init is roughly 10-40 s (estimate; it decodes the needed textures against the no-op GL), about 300-700 MB RAM (estimate), and then roughly milliseconds per vector. 10k map seeds take well under a minute. It runs once per content change, never per simulated run.
Rejected alternative: the jar at sim time would cost roughly 1-10 ms per run decision over IPC. That is still small next to the fights; it loses on the other grounds above, not on CPU.

### Code estimate

All estimates.
- Rust: about 2,500-3,500 lines (rng 200, map 400, state and obs 500, interpreter 900, rewards, shop and Neow 600, bindings 300, parity tests 400).
- JSON data: about 2,000-2,500 lines (Act 1 events about 28 x 40, Neow 200, shop 100, rewards 120, map 40, relic run rows 45 x 5, wording entries 150).
- Java oracle: about 600-900 lines, plus stubs if needed.
- Python: about 1,000-1,300 lines (run_layer.py observe and decide 400, gauntlet run-sim mode 300, replay and parity tests 400, real_game_run.py shrinking by about 100).
- Generated vectors: about 10-50 MB of jsonl. They are regenerated by `jar-oracle vectors`, which is the clean command; keep them in gitignored target/run-vectors and commit only a small sample set under engine/tests/data.

### Cheapest probe

About 150 lines of Java in the scratchpad, compiled with JBR's javac --release 8 against desktop-1.0.jar and run with the game's jre/bin/java.exe:
- new HeadlessApplication(empty listener)
- Gdx.gl = Gdx.gl20 = Proxy.newProxyInstance(GL20) returning zeros
- Settings.seed = the seed of one logged run in results/real-game/*/states.jsonl; ascensionLevel = 20
- CardCrawlGame.languagePack = new LocalizedStrings(); CardLibrary.initialize(); RelicLibrary.initialize()
- AbstractDungeon.generateSeeds(); new Exordium(new Ironclad(...), new ArrayList())
- print AbstractDungeon.map's node symbols and NeowEvent's options
- diff them against that run's MAP and Neow screen_state
Pass means the oracle route is open. A stack trace names the first class to stub.

### Build steps

| Step | Size | Check |
|---|---|---|
| Probe the headless jar. A Java harness of about 150 lines in tools/jar-oracle/: HeadlessApplication, a Proxy GL20, LocalizedStrings, CardLibrary/RelicLibrary init, new Exordium(seed), then dump the map and Neow options | S | Its output equals the MAP and Neow screen_state of 5 logged real-game runs with the same seed. If it fails, record which constructor fails and switch to shadow stubs, or run under ModTheSpire with the window hidden |
| Port the game RNG to engine/src/run/rng.rs: GameRng (RandomXS128 with the murmur seed and counter, every call form), JavaRandom plus Collections.shuffle, the RunRng stream set, and the RunChance trait with GameRng and enumerate drivers | S | engine/tests/run_parity.rs: 10k oracle RNG sequences identical, including setCounter and copy |
| Map generator in Rust with content/run/map.json parameters | M | 10k oracle seeds give identical nodes, edges and room symbols; the maps in all logged runs match |
| RunState, RunObs, RunSim bindings, and reward tables in rewards.json: card rarity with its rare offset, potion drop, gold, relic tiers and pools, chest | M | oracle vectors per seed and room sequence; test_run_replay.py matches every CARD_REWARD, COMBAT_REWARD and CHEST in the logs along the logged paths |
| Run vocabulary interpreter, then the Act 1 events extracted one by one by a Claude workflow (decompile, data row, oracle vectors, test), with ? room resolution through EventHelper.roll | L | one vector test per event over a spread of states and options, including stream counts consumed; wording.rs clean; every logged EVENT screen matches |
| Neow, shop and boss relic as data | M | oracle vectors plus a log-replay match of the Neow, SHOP and boss-relic screens |
| Relic run hooks: the R2 draft's 45 relics as `run` rows in act1-relics.json, read by the same interpreter | M | per relic, an oracle vector (onEquip, campfire options, reward size) plus the R2 draft's 'relics off is byte-identical' test |
| Bridge: scripts/run_layer.py observe() and decide() holding today's rules; real_game_run.py reduced to command adapters | S | the observe(gs) RunObs equals the RunSim RunObs on every logged screen; live runs keep RUN_RULES behaviour, bumped once for the move |
| gauntlet.run() run-sim mode: whole Act 1 runs with RunSim between fights and play(specs) for fights. This hands over to the backlog-83 decision maker | M | an old setting is still byte-identical; a seeded full-run smoke test; first paired read of decide() against a variant |

### Improves on sts_lightspeed

- Content is data, not C++: lightspeed's events live inline in GameContext.cpp (114 KB, with TODOs). Here every event, Neow option, shop slot, reward table and relic run hook is a JSON row that official, custom and generated content load the same way.
- Each item is proved against the installed jar by an automatic oracle vector, and every logged real-game run checks it again. Lightspeed's '100% RNG accurate' rested on hand-checking.
- Exact averaging is built in: one procedure runs seed-exactly with GameRng or as an exact distribution with enumerate(). Lightspeed can only roll, and its tree search assumes it knows the RNG state.
- Honest information by construction: RunRng sits outside RunState, things roll when seen, and the planning API never reads the game streams. Lightspeed's search reads the RNG.
- One observation type and one decide() for the simulator and the bridge, with a replay test as the contract. Lightspeed has no real-game bridge.
- Small code: only the map algorithm, the RNG and an interpreter are code (roughly 2.5-3.5k Rust lines, estimate), against lightspeed's roughly 150 KB of hand-written out-of-combat C++.
- Records RNG consumption per stream in every vector, so the places a fight disturbs a run stream show up, instead of silent drift.

### Borrows


### Risks

- Headless init may fail beyond the no-op GL: AbstractDungeon's static block builds TopPanel and the screens, FontHelper's FreeType init, UnlockTracker/HeadlessPreferences writing prefs (point them at a scratch dir and force all unlocks), and Steam integration if anything touches it. Mitigation: shadow stub classes or ModTheSpire with the window hidden (sts-ironclad-agent's route). The probe answers this in about an hour.
- Event effects run through effectList. ShowCardAndObtainEffect obtains the card only as its update advances, so the harness must tick effects with a nonzero MockGraphics delta. getCurrRoom() must hold a room for spawnRelicAndObtain.
- Cross-stream consumption: if our combat engine's relics, potions or cards consume potionRng, cardRng or relicRng differently from the game, everything after that fight diverges. Fights would have to report stream calls, or the replay check must accept divergence after such a fight.
- Unlock and profile state changes the pools (UnlockTracker). The oracle must use the same all-unlocked A20 profile as the owner's game, or the vectors disagree with the logs.
- Conflict with the in-flight R2 draft (docs/specs/run-layer-relics.md), which puts the run vocabulary in Python in gauntlet.py. Recommended: keep its data rows and triggers, and interpret them in engine/src/run/ so the bridge shares them. This needs the manager's agreement before either is built.
- Some outcomes are not seed-determined in the game either (transformCard's new Random(), returnColorlessCard()'s global shuffle). They get distribution tests only.
- Legal and size: the decompiled source and the jar stay out of git. Only facts extracted as data rows are committed, and the oracle loads the user's installed jar at run time.
- Order: docs/direction.md 'Avoid' and backlog 83 put the decision maker after content. This plan builds content and simulator first and does no decision-maker work beyond moving today's rules.

## C. Thin run layer shared with the bridge (Python)

**Shared run layer (scripts/run/): one run state and choice interface, two backends (simulator, real game), content as rows.** A small Python package holds the run state, a closed list of run effects, a Chance interface that can list outcomes exactly or sample them, and a view/world split. Content tables are data in content/run/*.json and in pack sections. Two backends sit behind one interface: the simulator and the CommunicationMod bridge. The run policy, logs, reports and a log-replay fidelity check are written once. It grows from gauntlet.run() and the R2 draft in steps you can measure, and a log-replay harness against the 70+ logged real runs checks each step.

### Architecture

Where the code lives: Python, in a new package scripts/run/ next to gauntlet.py and real_game*.py. Rust is used only for fights, as today. Why Python: the run layer's own cost is about 1 ms a decision (estimate), so roughly 0.1 s a run against 8 to 180 thread-seconds of fights. The bridge, the gauntlet and the choosers are already Python. Claude-written per-item tests are fastest to write and check in Python. And no maturin rebuild or .pyd swap (AGENTS.md) is needed to add an event. The vocabulary is pure data with a small interpreter, so moving it to Rust later is mechanical if a fast fight model ever makes Python the bottleneck. Measure that before moving anything.

Components:
1. run/state.py. Two parts.
   - RunState (seen by the player): hp, max_hp, gold, deck (names in sts.base_name / upgrade_name form, as gauntlet.upgrade uses), relics [(id, counter)], potions, act, floor, map (nodes with symbol, x, y, children, the same shape as CommunicationMod's gs["map"], so map_command's segments() works unchanged), position, act_boss (visible in the game), and screen (kind plus a list of Option{label, rows}).
   - World (hidden): the RNG streams, pre-rolled lists (monster list, boss), and the event pool's remaining list. RunState.view() returns a frozen RunView, and the policy receives only that. Equality is judged on the RunView (the afterstate rule in docs/concept.md and AGENTS.md).
2. run/chance.py. A Python copy of the engine's Chance trait and enumerate() from engine/src/rng.rs: below(n), chance(p). Implementations:
   - Sampler(rng).
   - Enumerator(cap): reruns a procedure with forced branches and returns [(outcome, p)]. It switches to sampling K draws when the branch count passes the cap.
   - JavaStreams: the game's com.megacrit.cardcrawl.random.Random (libGDX RandomXS128 plus a counter) for seed-exact replays, in run/jrandom.py.
   Every random run procedure (a reward roll, a ? room roll, an event coin flip) is written once against Chance. The simulator, exact planning and seed-exact replay all use that one copy.
3. run/atoms.py. The closed run vocabulary as functions (state, args, chance) -> state. It starts from R2's list: GainMaxHp, LoseMaxHp, Heal, HealFull, Damage, GainGold, LoseGold, ObtainRelic{tier|id}, ObtainPotion, AddCard{id|pool,rarity,upgraded}, AddCurse, Pick{source: deck, filter, n, then: Remove|Upgrade|Transform|Duplicate}, RewardSize, UpgradeAdded, ExtraReward, RestOption, NoGold, NoPotions, NoRest, NoSmith. It adds Fight{encounter, rewards} (handed to the fight backend), Roll{table} (a chance branch over rows), Screen{id} (an event's next page) and Leave. A pick is a decision point (descriptor plus candidates from a source with a filter; a multi-pick is single picks plus Done), the same shape as docs/extending.md's in-fight decisions. Each atom name goes in a Python ATOMS list. A test, scripts/tests/test_run_wording.py, names any atom without words in content/wording.json, the same rule as registry::element_names() and engine/tests/wording.rs. The explorer can then word run content.
4. run/content.py. Loads content/run/{rewards,map,shop,neow,events,encounters_act1}.json plus the run sections of packs (a pack's "events", "run" keys on relics, "shop" overrides). It validates every row against ATOMS, hashes the loaded set, and records the hash in each run file, as packs are recorded today.
5. run/flow.py. The run's screen machine: Neow, Map, room (Monster / Elite / Event / ? / Shop / Rest / Treasure / Boss), Rewards, BossRelic, end of Act 1. Its interface:
   - legal(state) -> [Option]
   - apply(state, i, chance) -> state
   - outcomes(state, i, cap) -> [(state, p)], which uses Enumerator
   - needs_fight(state) -> FightSpec
   Relic triggers (OnPickup, RestEnter, RestOptions, CardReward, CardAdded, FightWon, ShopEnter, RoomEnter, ChestOpen) fire from the hook points in flow.py, using the relic's "run" rows.
6. Backends, all with the same interface (view(), legal(), step(i)):
   - run/sim.py SimBackend: flow.py plus a FightBackend.
   - run/bridge.py GameBackend: parses CommunicationMod's gs into RunView and Options, and turns an option index into a command. It wraps today's Bridge.outside().
   - run/logback.py LogBackend: replays results/real-game/*/states.jsonl, for the fidelity check below.
7. FightBackend: EngineFights calls ladder.play_bench with the fight specs gauntlet.run builds today, plus relics= for sts.Combat, as R2 proposes. LogFights takes the logged fight results (fights.jsonl hp_end). A later SurrogateFights is a learned (won, hp_end) predictor, the CPU lever for run learning in build step 9.
8. run/policy.py. choose(view, options) -> index.
   - RulesPolicy: real_game_run.py's event_command, map_command, reward_command, rest_command, grid_command and boss_relic_command, rewritten on RunView.
   - SimCardPolicy: gauntlet.sim_offer_scores / sim_score, which real_game.Bridge.card_pick already copies by hand; it becomes this one function.
   - A learned policy later.
9. run/record.py. One decision row format {view hash, options, scores, pick, seconds}, shared by real_game.py's decisions.jsonl and sim run files, so real_game_report.py and gauntlet `read` can report both.

How state, choices and chance look: a state is a RunState (view plus world). A choice is an index into legal(), and each Option carries the rows it applies, so options are compared by the afterstate they reach. Chance is never stored in the view. It is rolled at the moment it becomes visible: a ? room's type when you enter, a card reward when its screen opens, an event's outcome when you pick. This follows the information principle in docs/extending.md.

### Content model

Everything is rows in the closed vocabulary. Numbers can depend on ascension: {"base": x, "a15": y}, read with the run's ascension.

- Event (content/run/events.json, or a pack's "events"): {id, act: [1], pool: "exordium"|"shrine"|"one_time", when: [conditions EventHelper checks, e.g. {"gold_at_least": 35}, {"floor_above": 6}, {"hp_share_at_least": 0.5}], start: "intro", screens: {intro: {text_key, options: [{label, requires?, rows: [...]}]}, ...}}.
  Example, Big Fish: intro options Banana [Heal {"max_hp_share": 0.33}], Donut [GainMaxHp 5], Box [ObtainRelic {"tier": "random"}, AddCurse "Regret"], each followed by Leave.
  Example, Golden Idol: Take [ObtainRelic "Golden Idol", Screen "trap"], trap options Outrun [AddCurse "Injury"], Smash [Damage {"max_hp_share": {"base": 0.25, "a15": 0.35}}], Hide [LoseMaxHp {"max_hp_share": {"base": 0.08, "a15": 0.10}}].
  A coin flip is Roll {table: [{p: 0.5, rows}, ...]}.
  Event fights (Dead Adventurer, Mushrooms) use Fight {encounter, rewards}.
  The few events with odd mechanics (Match and Keep, Wheel of Change, The Library, N'loth, We Meet Again, Falling) get one named atom each where the vocabulary can't say it. That atom is a vocabulary addition with its words, tier B in docs/extending.md, never inline code.
- Relic run part: a "run" list on the relic's entry in content/packs/act1-relics.json, as R2 proposes: [{trigger, rows}]. Examples: Strawberry [{OnPickup, [GainMaxHp 7]}], Question Card [{CardReward, [RewardSize 1]}], Regal Pillow [{RestOption, ...}]. Relic pools come from the existing rarity field plus a "class" field.
- Shop (content/run/shop.json): the slot layout (2 attack, 2 skill, 1 power colour cards with one on sale, 2 colourless, 3 relics with a shop-tier slot, 3 potions, a removal), price bands by rarity and kind, the jitter range on merchantRng, the A16 multiplier, the removal price as base plus a step per removal, and the sale share. Membership Card, The Courier and Smiling Mask act through ShopEnter rows.
- Reward tables (content/run/rewards.json): card rarity odds per room kind, the rarity offset rule (start, the step per common, reset on a rare, floor), the upgrade chance per act and ascension, gold bands per room (A13 boss gold), potion drop chance and its ±10 ramp, relic tier odds for elites and chests, chest sizes, and the boss relic count. Claude reads each constant from AbstractRoom, AbstractDungeon and the reward classes, with a test that names the jar method.
- Neow (content/run/neow.json): four slots, each a list of candidate rewards as rows. Slot 3 pairs a drawback with a bonus, with the jar's condition lists. The boss swap is its own slot. The A-level limits (an A15+ start) come from NeowEvent / NeowReward.
- Map (content/run/map.json): parameters only (rows 15, columns 7, path count 6, room shares shop / rest / event / elite with the ascension elite factor, fixed rows: 0 monster, 8 treasure, 14 rest, min row for elites and rests, adjacency bans). The generator algorithm is code in run/map.py (an estimated 250 lines), checked seed-exact. A custom map style is a different parameter set or a fixed list of nodes. The gauntlet's 11-floor SHAPE becomes one such fixed line map (content/run/maps/gauntlet11.json).
- Encounter lists: content/run/encounters_act1.json holds the weak and strong pools with weights, the first-N-weak rule, the no-repeat rule and the elite and boss pools. Pack hallway encounters (gauntlet.pack_hard) join the pools the same way.

What a new custom element needs:
- A new event, relic run part, shop item or Neow option made from existing atoms: one row in a pack, no code. It loads the same way official ones do (decision/registry-first).
- A new atom: a function in run/atoms.py, its words in wording.json and a test (test_run_wording.py names the miss).
- Generated run content: scripts/gen_content.py can write events as boon-plus-bane pairs from the atom list, the run-level version of the goal-1 yardstick.

### Fidelity plan

Three layers, each automated so Claude can do it item by item.

1. A per-item test against the jar. For each event, relic run part, Neow reward and table, Claude decompiles the class (memory decompile-game-jar.md; decompiled sources for MapGenerator, NeowEvent, NeowReward, EventHelper, AbstractDungeon, BigFish and GoldenIdolEvent already sit in the survey scratchpad's oracle/src) and writes the data row. It also writes a test in scripts/tests/test_run_<kind>.py that names the jar method and checks the jar's numbers (for example GoldenIdolEvent's A15 damage share), and checks the outcome distribution with Enumerator. The work is one item per task, as a queue.

2. Seed-exact checks where the game's streams are separate and few other things consume them. This rests on run/jrandom.py, a copy of the game's Random (RandomXS128 plus a counter), checked against the jar itself. Run a 20-line Java class with the game's Java 8 JRE and desktop-1.0.jar on the classpath, calling new com.megacrit.cardcrawl.random.Random(seed).random(n). That class only needs gdx's RandomXS128, which is in the jar. Seed-exact targets:
   - The map: mapRng from seed plus act, against gs["map"] (60 nodes with symbols and edges) for each of the 90 logged seeds.
   - The boss: act_boss is logged.
   - The monster and elite lists (monsterRng), against the encounter order in fights.jsonl.
   - Neow's options (NeowEvent uses new Random(Settings.seed)), against the 270 logged Neow states.
   - The ? room type roll, against which room each logged ? became.
   Probably seed-exact, but only after a probe: the first card reward of a run. cardRng order depends on the card pool's order (CardLibrary iteration), which can be pulled from the jar once and stored as data.
   Distribution-exact only, and fine that way: later card rewards, potions and gold after the run's choices diverge, shops (merchantRng after other draws), and event outcomes on miscRng / eventRng after the first divergence.

3. The log-replay harness, run/replay_check.py. It steps LogBackend and SimBackend side by side: each logged choice from states.jsonl is applied to the simulator, fights come from LogFights, and every screen the simulator opens is compared to the logged one. Per run and per kind (map, Neow, reward, event, rest, chest, boss relic, shop) it reports the first divergence, plus counts: screens matched exactly and screens matched in support (the logged outcome was among outcomes() with p > 0). A support miss is a bug. An exact miss on a stream marked seed-exact is a bug. An exact miss on a stream marked distribution-only gets a chi-square pooled over the logs. It runs on each new real-game run, about 30 a day. This catches drift without any extra game time.

Mismatches with the brief:
- The bridge doesn't log shops. real_game.Bridge.outside() sends proceed/leave on SHOP_ROOM, and the logs hold 52 SHOP_ROOM states and no SHOP_SCREEN. Shop prices therefore can't be checked against the logs until the bridge opens the shop screen, records it and leaves. That is a small change to RulesPolicy (bump RUN_RULES).
- The logs hold 34 distinct events. The Act 1 events never seen yet are checked only against the jar until they turn up.

### Chance and hidden information

Exposure: every random step is a procedure on Chance. flow.outcomes(state, i, cap) runs it under Enumerator. If the branch count stays under cap (default 64, tunable), it returns the exact list [(afterstate, p)]. Otherwise it returns K samples with equal weight, marked sampled.
- Exact: a card reward's rarity per slot (3 slots, 3 rarities, the offset carried; the identities within a rarity are sampled), upgraded or not, a ? room's type (4 outcomes with the game's ramping shares), an event's coin flips, potion drop or not, a chest's size and tier, gold amounts (about 11 values each).
- Sampled: full card identities over the pool, a shop's whole stock, Neow's whole option set.
The planner can mix the two: exact over rarity, sampled within it.

Hidden information:
(a) The policy gets RunState.view() only. World (streams, pre-rolled monster list, the remaining event pool, the next ? ramp) is unreachable from RunView.
(b) In the simulator's default mode, outcomes are rolled at the moment they become visible (a ? room on entry, a reward when its screen opens), so nothing hidden even exists in the state. This matches engine/src/state.rs keeping RNG outside the state, and the information principle in docs/extending.md.
(c) The seed-exact mode, used only by replay_check and parity tests, holds JavaStreams in World. outcomes() for planning always uses the content's distributions, never the World streams, so a seed-exact run can't leak the future to the planner.
(d) A leak test, test_run_leak.py: two worlds with the same view history but different streams must give identical policy decisions and identical outcomes() lists.
(e) Things the player does see are in the view, as in the real game: act_boss, the map's symbols including '?' (not what each ? holds), and shop stock once inside.

### Shared with the bridge

Shared, one copy each:
- RunView and Option (run/state.py).
- The policies (run/policy.py: RulesPolicy, the sim card chooser, later learned policies).
- The decision row format and the reports (run/record.py, read by real_game_report.py and gauntlet `read`).
- The chooser's trial-fight code (gauntlet.sim_fights / sim_score, which real_game.Bridge.card_pick copies by hand today, with its own seeds and next_kind).
- The Chance-based outcome model, which the bridge can use for planning too.
- The content files, which the bridge needs to name relic effects for planning.

Different:
- The simulator's flow.py plus World.
- run/bridge.py's parse of gs into RunView and Options, and of an index into a command. It reuses real_game.card_of, namer and unselected; map nodes keep CommunicationMod's shape, so segments() and path_key() carry over as they are.

Migration: Bridge.outside() becomes view = bridge.parse(gs); i = policy.choose(view, options); send(bridge.command(gs, i)). Its error ladder (the proceed / skip / leave ways out) and GAME_OVER / stop_run handling stay in real_game.py. The equality check for the port: replay every logged out-of-combat state through the new RulesPolicy and assert the same command as the "send:" lines in log.txt and the picks in decisions.jsonl, so RUN_RULES stays 5. The simulator in turn runs RulesPolicy unchanged, so the same rules can be read in simulation and in the live game.

### CPU cost

Run layer (estimate): about 0.2 to 1 ms per decision in Python including Enumerator calls, about 100 decisions a run, so under 0.1 s a run. outcomes() with cap 64 costs at most about 64 procedure runs, still milliseconds.

Fights (from the brief): 12 to 17 a run at 0.5 to 1 s one turn deep (about 8 to 17 thread-seconds) or about 12 thread-seconds each two turns deep (about 150 to 200 thread-seconds). The run layer is therefore under 1% of a one-turn run and under 0.1% of a two-turn run.

The real cost driver outside fights is the choosers' trial fights, not the simulator. gauntlet.sim_choose plays (1 + 3 options) × 8 one-turn fights per reward, ×2 with the boss part: 32 to 64 fights, about 16 to 64 thread-seconds per card reward (estimate), or 200 to 700 thread-seconds over a run's 12 rewards. That exceeds the run's own fights. So the design leaves the run layer in Python and puts the CPU lever in the FightBackend slot: SurrogateFights, a small learned (won, hp_end) predictor trained on the engine fight records the ladder and gauntlet already produce, about 1 ms a fight (estimate). It is used for run-policy learning over 1e5 or more simulated runs, about 0.1 s each, roughly 1 to 3 hours on the dev machine (estimate). EngineFights stay the yardstick for headline reads.

### Code estimate

Estimates. Python, about 3.5k new lines:
- jrandom 80
- map 300
- state 300
- chance 150
- atoms 500
- content loader 200
- flow 600
- bridge parse 400
- policy port 300
- record 100
- replay_check 300
Plus about 1.5k lines of tests (about 100 small per-item tests). Python removed: about 150 lines (real_game_run.py's rules move into policy.py; real_game.Bridge.card_pick's copy of the sim chooser goes).

JSON data, about 2.5k lines:
- events 1200
- relic run rows 300 (on act1-relics.json)
- neow 150
- shop, rewards and map 250
- encounters_act1 100
- wording entries 300

Java: about 20 lines (a throwaway test harness for Random, in the scratchpad or scripts/tests/fixtures). Rust: 0 to 50 lines (only if sts.Combat doesn't already return relic counters after a fight, as R2 notes).

### Cheapest probe

Write run/jrandom.py (the game's com.megacrit.cardcrawl.random.Random over RandomXS128, about 60 lines) and a Python MapGenerator (about 250 lines, from the decompiled MapGenerator.java already in the survey scratchpad's oracle/src). Generate the Act 1 map for each of the 90 seeds in results/real-game/*/states.jsonl and compare it with the logged gs["map"] (60 nodes, symbols and edges). Check jrandom first against the jar with a 20-line Java class run by the game's Java 8 JRE. It costs one session and no CPU, and it answers yes or no on the foundation every seed-exact check needs (the RNG wrapper and the seeding). It also says whether the map, the most-used run screen with 1445 logged MAP states, can be simulated exactly.

### Build steps

| Step | Size | Check |
|---|---|---|
| Probe: run/jrandom.py (the game's Random) and run/map.py (MapGenerator from the decompiled source, parameters in content/run/map.json), checked against the Act 1 map of every logged seed | S-M (about 350 lines Python, 40 lines JSON, 20 lines Java test harness; estimate) | jrandom matches the jar's Random on 10k draws from 20 seeds (Java 8 JRE harness); the generated map equals gs['map'] (nodes, symbols, edges) for all 90 logged seeds |
| RunView, Option and run/bridge.py parse; RulesPolicy ported from real_game_run.py onto RunView; Bridge.outside() switched to it (RUN_RULES stays 5) | M (about 700 lines; estimate) | replaying every logged out-of-combat state gives the same command as log.txt's send lines and the same card picks as decisions.jsonl (0 mismatches); test_real_game_run.py passes |
| RunState, World, chance.py (Sampler, Enumerator), atoms.py with R2's vocabulary, flow.py on the fixed gauntlet11 line map with EngineFights; R2's run state (hp, max_hp, deck, relics with counters, gold) lands here, not inside gauntlet.run(), agreed with the R2 session | M (about 900 lines plus tests; estimate) | with relics off, gauntlet run() and the new SimBackend give byte-identical floor rows on 50 pinned sequences with the same play function; test_run_wording.py passes; Enumerator matches rng.rs enumerate on shared toy procedures |
| content/run/rewards.json and reward screens (card rarity with offset, upgrades, gold, potion ramp, elite relic tiers); R2's 45 relic run rows, with the ones R2 can do without the map (about 30) first | M (about 400 lines Python, 300 lines JSON, about 45 small tests; estimate) | each constant's test names its jar method; replay_check: 100% in support on logged COMBAT_REWARD / CARD_REWARD screens (947), chi-square on rarity at p>0.01; first card reward seed-exact on the 90 seeds as a stretch result, reported |
| Full Act 1 flow: monster, elite and boss lists (monsterRng), ? room roll, rest, chest, boss relic; replay_check.py with LogBackend and LogFights | M (about 600 lines; estimate) | encounter order and ? room types seed-exact on every logged run up to its first divergence; replay_check reports per-kind exact and support counts; boss_relic and chest screens 100% in support |
| Events: the Act 1 pool (Exordium, shrines, one-time events) as data rows, each extracted by Claude from its decompiled class with a test; a named atom only for events the vocabulary can't say | L in count, S per item (about 25 events, about 1200 lines JSON, about 25 tests; estimate) | per-event jar test; replay_check: all 34 logged event kinds 100% in support over the 662 EVENT states; the pool and conditions match EventHelper |
| Neow from NeowEvent / NeowReward as data | S (about 150 lines JSON, about 100 Python; estimate) | Neow options seed-exact against the 270 logged Neow states on all logged seeds |
| Shops: content/run/shop.json plus a bridge rule change: open the shop screen, record it, leave (RUN_RULES 6) | S-M (about 300 lines; estimate) | once logs include SHOP_SCREEN: prices in range and stock in support on 100% of logged shops; merchantRng seed-exact for a shop reached before any divergence, reported |
| Only then (backlog item 83, docs/direction.md 'Avoid'): SurrogateFights trained on existing engine fight records, and a learned run policy trained on simulated runs | L (separate spec) | surrogate vs engine: rank agreement on chooser decisions on held-out gauntlet sequences reported; the policy is read on the headline gauntlet with EngineFights, paired, and then live |

### Improves on sts_lightspeed

- Content is data: events, Neow, shop and reward tables and relic run parts are rows in a closed, worded vocabulary, so a generated or custom event loads like an official one. In lightspeed, events are inline C++ switch cases in GameContext.cpp (114 KB with TODOs).
- One Chance interface with an exact enumerator, copied from the engine's rng.rs, so the planner can average small chance exactly. Lightspeed only samples from RNG streams, and its search read the real stream (silverbot had to remove that cheat).
- The view/world split, plus outcomes rolled when they become visible, plus a leak test. Hidden run information is kept out of the state by construction, not by discipline.
- One implementation shared by the simulator and the real-game bridge: policies, logs and reports are written once. Lightspeed had no bridge; silverbot added one later as a separate path.
- A continuous fidelity check for free: log replay against the 30 real runs a day, with the first divergence reported per kind, plus a jar-derived test per item, written one item at a time by Claude.
- The fight backend is a slot (engine, logged fights, later a learned surrogate), so run learning can be cheap without changing the run code. Lightspeed always plays full fights.
- Seed-exact only where it is cheap and checkable (map, monster list, Neow, ? rolls); distribution-exact elsewhere. It does not chase 100% RNG accuracy across the whole run.
- Smaller: about 3.5k lines of Python plus about 2.5k lines of JSON (estimate) for Act 1, against lightspeed's roughly 4-5k lines of C++ out-of-combat code across all acts (estimate from file sizes).

### Borrows


### Risks

- A seed-exact chain breaks on one wrong or missing RNG draw (for example cardRng's pool order from CardLibrary's HashMap). The mitigation is that replay_check names the first divergence and every stream has distribution-exact as its fallback status.
- The closed vocabulary may creep: about 6 Act 1 events (Match and Keep, Wheel of Change, The Library, N'loth, We Meet Again, Falling) need named atoms. Each costs words and a test; together they may total 10-15 extra atoms (estimate).
- Collision with the R2 draft (untracked): if R2 builds its run state inside gauntlet.run(), step 3 has to lift it out. The design needs the manager to settle where R2 lands before R2 is built.
- Porting the rules may change live behaviour silently. Step 2's 0-mismatch replay of the logged states is the guard; any intended change bumps RUN_RULES.
- CommunicationMod shows less than the game in places (event body text, shop details only on the shop screen, Match and Keep's face-down cards), so the parse and the simulator's view can differ. The view must be defined by what the bridge can see.
- Logs are thin for rare events and for shops (none logged), so support checks rest on the jar tests alone until the logs fill in.
- A surrogate fight model can bias run learning (wrong HP prices for elites). Headline reads must keep EngineFights.
- The headless jar oracle (scratchpad oracle/src2 HeadlessApplication suggests someone tried) may not be able to run MapGenerator or events without rendering; the plan needs it only for Random, which needs just gdx.

## D. An abstract run model first (Python)

**Run model as data: an act described in JSON, one interpreter, chance as a swappable source.** A Python run interpreter reads acts, reward tables, shops, events, Neow and relic run-effects from content/run/*.json. It draws every random outcome through one Chance interface that can sample, enumerate exactly or replay what was observed. The simulator, the gauntlet and the real-game bridge all use it. It starts as a statistical model checked against the 70 logged runs, and a piece is made seed-exact only where a decision measurably changes.

### Architecture

Where each part lives (new files are marked NEW; all sizes are estimates):

1. DATA (content/run/, NEW). act1.json holds the map generator's parameters (rows, columns, path count, how room types are given out, the fixed treasure and rest rows, the elite share at A1 and above), the ? room odds and how they grow, the encounter pools (weak pool for the first fights, strong pool, elites, bosses, with their weights and no-repeat rules), the reward tables (card rarity odds per room group with the rarity offset's start, step, floor and reset; gold ranges per room group with the A13 boss cut; potion drop chance with its plus or minus 10 step; relic tier odds) and the shop table. events-act1.json holds the Exordium and shared events. neow.json holds Neow's option categories. Each relic's run part is a `run` key on its existing entry in content/packs/act1-relics.json, the trigger and effect rows that docs/specs/run-layer-relics.md already proposes. gauntlet.json (NEW) describes today's SHAPE in scripts/gauntlet.py as a degenerate act: a fixed 11-room line with the EASY, HARD, ELITES and BOSSES pools.

2. INTERPRETER (scripts/runsim/, NEW Python package).
   - content.py loads and checks the run data and resolves names against the engine's packs through sts.
   - state.py holds RunState: hp, max_hp, gold, deck, relics as (name, counter), potions, floor, map and position, plus the counters the player could work out from what has happened (rarity offset, ? room odds, events already seen, last encounters). It holds no RNG.
   - chance.py is a Python copy of engine/src/rng.rs: a Chance with below(n) and chance(p), the samplers Rng and JavaRandom, enumerate(f) (the same replay-path enumerator as rng::enumerate) and Observed (for the bridge: it returns the outcome the game showed).
   - effects.py interprets a closed run vocabulary: GainGold, LoseGold, Heal, HealOf, LoseHp, GainMaxHp, LoseMaxHp, ObtainCard, CardReward, Remove, Upgrade, UpgradeRandom, Transform, Duplicate, ObtainRelic, ObtainPotion, AddCurse, Fight, OpenShop, Roll [{p, effects}], PickFrom {pool, filter}, Choose [options] and Leave. The combat vocabulary's names are reused where they mean the same thing.
   - generators.py holds map(), room_of_question(), encounter(), card_reward(), gold(), potion_drop(), relic_tier(), shop_stock() and event_pick(). Each is a function f(state, chance, tables).
   - sim.py advances N runs together, each to its next fight or decision. It hands all pending fights to the same play(specs) callable that gauntlet.run() takes today, so one batch fills the threads.

3. DECISIONS follow docs/extending.md: a RunDecision is a descriptor plus candidates, and each candidate is (label, effect rows). The chooser picks among the states those rows lead to (afterstates). Two candidates that reach the same state merge, as the AGENTS.md rule says. Choosers live in scripts/runsim/choosers.py. RuleChooser is real_game_run.py's map, event, rest, reward, grid and boss-relic rules rewritten over RunDecision. The gauntlet's sim, value and vrun choosers move over unchanged in signature. A learned chooser comes later.

4. FIGHTS are outside the run layer, behind play(specs). There are three ways to settle one: two turns deep (about 12 thread-seconds), one turn deep (about 0.5 to 1 s), and a fast estimate from the value net at the fight's start state (the existing gauntlet.net_values and value_parts, in milliseconds).

5. RUST: about 20 lines. A `run_effect` group in registry::element_names() lists the run vocabulary, so engine/tests/wording.rs makes every run element carry its words in content/wording.json and the explorer can word it. The run interpreter itself stays in Python. Fights cost about a thousand times more than run decisions, so Rust would buy nothing until fights are settled by the fast estimate. Even then the run layer at about 1 to 5 ms a decision (estimate) gives roughly 50k or more runs an hour on the dev machine.

### Content model

Every element is a row. Every random part is a Roll or a PickFrom inside the row, which is what lets enumerate() average over it exactly.

- EVENT: {id, acts, pools: ["act1-events" | "shrines"], when: {floor_min, gold_min, hp_min, not_seen, relic_absent ...}, options: [{label, requires: {gold>=n, has_card_type ...}, effects: [...]}]}. Option labels are the game's own button text, so the logged EVENT screens can be matched to them.
  - Coin-flip or few-outcome events use Roll. Example: Wheel of Change is Roll over six effect lists at 1/6 each.
  - Fights use {"Fight": {"encounter": "...", "rewards": {...}}}, for example Dead Adventurer and Mushrooms.
  - Repeated-try events (Scrap Ooze, the Golden Wing chain) use a Choose that repeats with a counter in the event's local state, still built from the closed vocabulary.
  - One event cannot be written as rows yet: Match and Keep, a memory mini-game. It is modelled as its outcome distribution under a fixed policy (a Roll over how many pairs are found) until the owner wants it played.
- RELIC: the pack entry gains "run": [{trigger: OnPickup | RestEnter | RestOptions | CardReward | CardAdded | FightWon | ShopEnter | ChestOpen | RoomEnter, effects | modifies: {reward_size: +1, upgrade_added: "Attack", no_gold: true ...}}]. These are exactly R2's triggers. Relic pools are lists by tier in act1.json that packs can join.
- SHOP: a stock spec in act1.json:
  {cards: [{type: Attack, n: 2}, {type: Skill, n: 2}, {type: Power, n: 1}, {colorless: uncommon}, {colorless: rare}], relics: [{tier: roll}, {tier: roll}, {tier: shop}], potions: 3, removal: {base: 75, step: 25}, sale: {n: 1, factor: 0.5}, price: {card: {common: [45,55] ...}, relic: {...}, potion: {...}}, ascension_factor: {A16: 1.1}}.
  All numbers are to be extracted from ShopScreen, StoreRelic and StorePotion; the ones given here are from memory and unconfirmed. A custom shop item is one row in a shop item pool: {item: "card" | "relic" | "potion" | "service", price, effects}.
- NEOW: neow.json lists the four categories, each a pool of options {label, cost: effects, reward: effects}, rolled with PickFrom. A custom Neow option is one row in a category's pool.
- REWARD TABLES: a CardReward row names a rarity table by room group, so a custom act or a generated element names its own table.
- WHAT A NEW CUSTOM OR GENERATED ELEMENT NEEDS: one JSON row in a pack that names the pools it joins. Only when it brings a new effect does it also need an entry in effects.py, a line in element_names() and its words in wording.json (tier B in docs/extending.md). scripts/gen_content.py can write run rows into the same packs it writes today, and they load the way official rows do.

### Fidelity plan

Three layers of checks, cheapest first.

(a) TABLE TESTS AGAINST THE JAR. For each table or event, a Claude Code worker does five things: (1) pulls the class out of desktop-1.0.jar with zipfile; (2) decompiles it with IntelliJ's ConsoleDecompiler, run on IntelliJ's bundled Java, as the memory note says; (3) writes the data row; (4) writes scripts/tests/test_run_<item>.py; (5) where the class runs headless, writes a short Java harness (scripts/jar_probe/, compiled with jbr javac --release 8 and run on the game's own Java 8 JRE) that calls the jar's method with fixed seeds and prints the outcome distribution, which the test compares with enumerate() over the data row.
   The classes:
   - AbstractDungeon: rollRarity, getRewardCards, returnRandomRelicTier, the gold reward code, the potion chance
   - MapGenerator and RoomTypeAssigner
   - EventHelper.roll (the ? room odds) and each event class's buttonEffect
   - ShopScreen, StoreRelic, StorePotion
   - NeowReward
   - each relic's onEquip and its other run hooks
   Where a class needs the game initialised and won't run headless, the test checks the row against a hand-written reading of the decompiled code, and against the logs when the logs have that item.

(b) STATISTICAL TESTS AGAINST THE REAL-GAME LOGS (results/real-game/*/states.jsonl, 70 runs, about 90 seeds). A scripts/runsim/logstats.py reads the logs and compares the model with them using a chi-square test or an exact-interval check:
   - map symbols per row; a first count over all maps gave M 2178, ? 1097, R 899, E 560, T 358, $ 264
   - rarity by room group; a first raw count gave COMMON 1479, UNCOMMON 1058, RARE 313, which still includes repeated screens to remove
   - gold per reward by room type
   - the potion drop rate
   - what ? rooms turned into
   - event frequencies, Act 1 floors only, because the logs include Act 2 events (Vampires, Nest, N'loth)
   - each event's option labels against its row
   The sample is small: rarity can be checked to about plus or minus 2 percentage points (estimate), but single events (about 5 to 30 sightings each) only for gross errors.
   Shops have no data: the bridge walks past them (MAP_RANK puts $ near last), so the logs hold 52 SHOP_ROOM states and no shop screen. Shop checks need the bridge to step in and leave a few times. That is a bridge change for another session, not part of this design.

(c) SEED-EXACT, ONLY WHERE IT PAYS. The rule: make a piece exact when a paired read shows a run decision changing under the abstract and exact versions, or when exactness costs almost nothing to test.
   - Map: the cheap candidate. The game builds it from its own java.util.Random seeded from the run seed, and the logs carry seed and map for about 90 seeds, so a 90-of-90 exact match is a direct test. Exactness gives decisions nothing, though, since the player sees the whole map anyway.
   - Card rewards, gold and potions can become exact the same way, by giving the JavaRandom Chance the game's per-purpose streams (cardRng, treasureRng, potionRng, merchantRng, eventRng, monsterRng, relicRng, miscRng) and calling in the jar's order. Each such upgrade comes with a test that reproduces the logged rewards of all 70 runs from their seeds.
   - Exactness is a testing mode only. The chooser never sees the seed.

BRIDGE CHECK: runsim/observe.py plus RuleChooser replays every logged decision state and must give the logged command (decisions.jsonl, RUN_RULES 5). This proves the shared chooser before the bridge switches to it.

### Chance and hidden information

Outcomes are rolled when they are revealed, as in engine/src/state.rs and docs/extending.md's information principle. RunState never holds an unrevealed outcome:
- the encounter of a room is rolled on entry;
- a ? room's type is rolled on entry, from the odds counters;
- a reward's cards, gold and potion are rolled when the reward screen opens;
- an event is drawn from the remaining pool when its room is entered, and its outcome when an option is picked;
- shop stock is rolled on entry.
The game builds its monster list and event order ahead of time. Rolling each one in turn, given what has already been seen, gives the same distribution because the game generates them in the same order under the same no-repeat rules. The counters the game keeps (rarity offset, ? room odds, potion chance) are functions of what the player has seen, so keeping them in the state leaks nothing. The map and the boss are visible in the game, so they are visible here.

Small chance is enumerated exactly. Every generator is f(state, chance), so chance.enumerate(f) gives the exact outcome distribution wherever the branching is small:
- a card reward's rarities: three slots at three rarities, at most 27 paths, fewer after merging;
- an event's coin flip or die roll;
- the potion drop;
- the gold range, or a few buckets of it;
- the elite relic tier;
- the next ? room's type.
Where the number of outcomes is large (which cards inside a rarity, shop stock, the map itself), a chooser looking ahead enumerates the small rolls and samples the large ones, with a fixed per-run sample stream so every option faces the same samples (the paired approach sim_fights uses today). With the same three modes the simulator samples, a chooser looks ahead exactly where it can, and the bridge runs the same code with Observed.

### Shared with the bridge

The two share everything except where an outcome comes from: the data files, RunState, the effect interpreter, the generators, the RunDecision builder and the choosers.
- runsim/observe.py turns a CommunicationMod game_state (the fields read in real_game_run.py: screen_state.options, next_nodes, map, rewards, cards, relics, gold, current_hp, max_hp, floor) into a RunState and a RunDecision whose candidate labels match the game's options. A second function turns the chosen candidate back into a `choose i`, `proceed`, `skip` or `confirm` command.
- real_game_run.py's event_command, map_command, reward_command, rest_command, grid_command and boss_relic_command become RuleChooser over RunDecision, with the same rules and the same RUN_RULES number until a rule changes.
- During a real run, a chooser looking ahead uses the same generators to estimate the future: the next card reward's rarities enumerated, ? room odds from the state's counters.
- The bridge's logs feed logstats.py's checks.
So a rule tuned on simulated runs is the rule the bridge plays, with no second copy to keep in step.

### CPU cost

All figures are estimates.
- Run layer in Python: about 100 decisions per Act 1 run. Under the rule chooser that is roughly 0.1 to 0.5 s per run. Enumerating a card reward's rarities adds a few ms.
- Fights per run, about 15 of them:
  - two turns deep: about 180 thread-seconds, so the run layer is under 0.3% of a run;
  - one turn deep: about 8 to 15 s, so the run layer is about 1 to 5%;
  - value-net estimate at the fight's start: about 15 × 5 to 20 ms, so the run layer becomes most of the cost, and runs reach roughly 30k to 100k an hour on the dev machine.
- Choosers that look ahead with sim fights (sim_choose: 8 fights per option per horizon part) dominate everything else; one card pick there costs about 32 one-turn fights.
- The plan for CPU time: tune and learn the run layer on runs whose fights are settled one turn deep or by the value-net estimate. Check the winning setting on two-turn runs with the gauntlet's paired protocol (protocol_verdict). Check the value-net estimate's error against one-turn fights on a held-out set before trusting it for any decision.

### Code estimate

All estimates.
- Python: about 2,500 to 3,500 new lines. Interpreter and effects about 600, generators about 500, sim loop about 400, observe and RuleChooser about 500, logstats about 250, tests about 1,000 to 1,300 (one small test per event, relic and table).
- JSON data: about 2,000 to 4,000 lines (act1.json about 300, about 28 events at about 40 to 80 lines each, neow.json about 150, gauntlet.json about 40, 45 relic `run` keys about 300).
- Java harness: about 200 to 400 lines (scripts/jar_probe/).
- Rust: about 20 lines (the run_effect group in registry::element_names()) plus the words in content/wording.json.
- Removed or thinned: gauntlet.run()'s fixed SHAPE loop and real_game_run.py's rules move into runsim, net about -200 lines.

### Cheapest probe

Write logstats.py first (in the scratchpad, about half a day): decode every results/real-game/*/states.jsonl, keep Act 1, remove repeated screens, and count rarities by room group (hallway, elite, event), gold per reward by room type, the potion drop rate per fight, ? room outcomes, map symbols per row, and Act 1 event counts. Put next to them the numbers decompiled from AbstractDungeon (rollRarity and the reward code), RoomTypeAssigner and EventHelper. A raw pass over the logs for this survey already gave map symbols M 2178, ? 1097, R 899, E 560, T 358, $ 264; card-reward rarities COMMON 1479, UNCOMMON 1058, RARE 313 (repeated screens still included); 270 Neow screens and Act 2 events present (so filter by act); and 52 shop-room states with no shop screen. If the abstract tables match these counts within error, the abstract-first plan holds and step 2 can start. A second half-day probe: try calling MapGenerator from the jar headless on the game's Java 8 JRE for the about 90 logged seeds. If it works, the jar harness for per-item tests is viable.

### Build steps

| Step | Size | Check |
|---|---|---|
| Log-statistics probe: scripts/runsim/logstats.py reads results/real-game/*/states.jsonl, keeps Act 1 only, removes repeated screens, and prints map symbols per row, rarity by room group, gold per reward, potion drop rate, what ? rooms turned into, and event counts. Next to them it prints the jar's numbers, extracted for these few tables only (rollRarity, the gold code, the potion chance, RoomTypeAssigner, EventHelper.roll). | S (about 1 day) | A table with each figure from the model beside the log's, with its p-value or interval; every gap is explained or listed |
| Core: RunState, chance.py (Rng, JavaRandom, enumerate, Observed), effects.py with the closed run vocabulary, content.py loader, and the run_effect group in registry::element_names() with its words in content/wording.json | M | Tests: enumerate sums to 1 and matches rng::enumerate on a shared toy function; cargo test --test wording names no missing words; a loader test refuses an unknown effect |
| The gauntlet as an act: content/run/gauntlet.json replaces SHAPE and POOLS, and gauntlet.run() calls runsim.sim with the same hooks (reward, rest_hook, remove_hook, path_hook, starts) | M | Existing gauntlet files replay byte-identical on their seeds (one pinned sequence, as R2's spec asks); golden passes |
| R2 (docs/specs/run-layer-relics.md) is built on RunState and effects.py instead of its own run state: the 45 relics' `run` keys | L (that spec's own size) | That spec's per-relic tests, run through effects.py |
| Act 1 proper: map generator, ? rooms, encounter pools with no-repeat rules, card, gold, potion and relic-tier rewards, chests, rest sites, from act1.json | M | logstats.py comparison within tolerance; jar harness distributions where headless; optional exact map for all about 90 logged seeds |
| Events as data, one worker per event class (about 25 to 30 reachable in Act 1, estimate), each with test_run_event_<id>.py | L, done in parallel | Per event: option labels match the logged EVENT screens; outcome distribution matches the decompiled buttonEffect (jar harness or hand reading) |
| Shops and Neow from ShopScreen, StoreRelic, StorePotion and NeowReward | M | Price ranges and stock types against the jar; against the logs only once the bridge visits shops (a separate bridge change) |
| Bridge adapter: observe.py plus RuleChooser; real_game_run.py's functions become thin wrappers | M | Replaying all 70 logged runs' decision states gives the logged commands (RUN_RULES 5), 100% |
| Only after the steps above (backlog item 83, direction.md 'Avoid'): tune and learn run decisions on simulated runs, fights settled one turn deep or by the value-net estimate, checked two turns deep with protocol_verdict | L | A paired read on the gauntlet protocol against today's rules (RUN_RULES 5), on simulated runs, then on the real-game bridge |

### Improves on sts_lightspeed

- Content is data, not code: sts_lightspeed writes each event inline in GameContext.cpp (114 KB, with TODOs). Here an event, relic run-effect, shop item or Neow option is a JSON row in a pack, and generated content loads the way official content does (goal 1)
- Exact averaging: sts_lightspeed only samples from seeded RNG. Here every generator takes a swappable Chance, so small chance (rarity rolls, coin flips, potion drops, ? room types) is enumerated exactly, as rng::enumerate already does in combat
- Honest information: sts_lightspeed's tree search 'knows the state of the rng'. Here outcomes are rolled at reveal and the state holds no RNG, so a chooser can't peek
- One implementation for both: the bridge runs the same interpreter and choosers with an Observed Chance, and every logged decision is replayed as a regression test
- Fidelity is measured, not assumed: statistical tests against 70 real runs, plus a test per item against the jar (a headless harness on the game's own JRE where possible), and seed-exactness added only where a decision changes
- Built for agents: one jar class becomes one data row plus one test, so Claude Code workers can extract events in parallel and a program checks their work
- CPU-aware: fights can be settled two turns deep, one turn deep or by a value-net estimate (the existing value_parts), so run-layer learning isn't capped at two-turn fight speed; sts_lightspeed has a single fight model
- The gauntlet becomes one act file, so existing reads, controls and VARY and MATCH_FIELDS stay comparable instead of a second simulator growing beside it

### Borrows

- sts_lightspeed (MIT) as a lead only: the order of calls in GameContext.cpp, Map.cpp, Shop.cpp and Neow.cpp to cross-check the jar reading, and its list of which RNG stream each roll uses (for the later seed-exact JavaRandom mode)
- engine/src/rng.rs rng::enumerate, the replay-path exact enumerator, rewritten in Python with the same algorithm
- scripts/gauntlet.py: run()'s batched play(specs) pattern, sim_fights' paired seed streams, value_parts and net_values as the fast fight estimate, protocol_verdict for paired reads
- scripts/real_game_run.py: all its rules become RuleChooser, keeping RUN_RULES
- docs/specs/run-layer-relics.md: its run state fields and trigger and effect vocabulary, adopted as RunState and effects.py
- silverbot and sts-ironclad-agent (docs/research/sts-ai-prior-art.md): both learned their run layer on a full-run simulator over thousands of games, the evidence that the simulator is the lever for goal 2

### Risks

- Jar classes may not run headless: most reward code reads AbstractDungeon's static state, CardLibrary and Settings, so the harness may need stubs or only work for MapGenerator. If so, tests fall back to a reading of the decompiled code plus the logs
- The abstract model can be wrong in small ways a statistic can't see but a decision can, for example duplicate exclusion inside one card reward, the rarity offset resetting on a rare, the elite's own rarity table, or Prismatic Shard or Question Card interactions. Mitigation: each such rule is written in the data and tested per item, not only checked statistically
- Small logs: 70 runs check rarity and room counts well but single events only for gross errors, and the logs hold no shop screens at all until the bridge visits shops
- Python speed becomes the limit once fights are settled by the value-net estimate (estimated tens of thousands of runs an hour). A Rust port of the interpreter is possible later behind the same data, at the cost of a second implementation to keep in step
- The value-net estimate is a proxy. Run decisions tuned against it may exploit its errors (direction.md warns against promoting by proxies), so the final check is always two-turn runs, paired
- Overlap with the draft R2 spec: if R2 is built on its own run state first, this design's step 4 becomes a migration. Agreeing on RunState and effects.py before R2 starts avoids the double build
- A few events (Match and Keep's memory game, Golden Wing's chain) need special atoms or an outcome-distribution stand-in, which strains the closed vocabulary rule in docs/extending.md

## Judges

### GOAL FIT: goal 1 (custom and generated run content loads as data, the same way official content does; weight 0

Ranking: data-engine, jar-oracle, thin-shared, abstract-first

| Design | Score | Reasons | Fatal flaw |
|---|---|---|---|
| data-engine | 9 | Strongest fit for goal 1. Run content goes into the same Rust registry and load_pack as cards, monsters and relics. A relic's run part is a `run` key on its existing pack entry, words come from wording.json, and the same pools decide eligibility. A custom or generated event, Neow option or shop rule therefore loads exactly like an official one, and gen_content.py can emit it. Because there is one loader, the explorer, the combat engine and any Rust planner all see the same content. Engine-owned primitives (MatchPairs and similar) are a closed set that data refers to by name, which keeps custom events data. Goal 2: the run layer costs under 1 ms a run; fights are batched across runs as today; a RunState is a few hundred bytes, so thousands of runs fit in memory. Honest information is the best of the four: RunState holds no RNG, the pre-rolled lists live in a separate Hidden that planners only get resampled, and a leak test checks that equal observations with different seeds give identical outcomes. Exact before sampling: an Exact backend with a per-site outcome cap reuses rng.rs enumerate(). Weaknesses under this lens: a new atom (not a new item) needs a Rust rebuild and a .pyd swap, which slows trying out generated content. It also has no cheap fight-settling option for learning; it only warns that planners must price fights with the value net. |  |
| jar-oracle | 8 | Nearly the same content model as data-engine: Rust, run content kinds parsed in registry.rs, atoms in element_names(), and a new custom element is rows only. Its 'option rows tell the agent what it gets' point serves goal 1 directly: the chooser reads a custom event's effects from data instead of scoring its words, so it works on content it has never seen. Exact enumeration is stated clearly, including which event is drawn from the eligible pool, and rarity is kept exact while card identity is sampled. Rolling each outcome at the moment the player sees it keeps hidden information out of the state. It scores lower than data-engine because much of its weight goes on the headless jar oracle, which only proves official content and does nothing for custom content. It also has no explicit way to redraw the hidden pre-rolled lists for planners, and like data-engine it has no cheaper way to settle fights for learning runs. |  |
| thin-shared | 7 | Content is rows in a closed, worded vocabulary, and a pack's events and relic `run` keys load through run/content.py, so custom content does work as data. Its map is parameters in content/run/map.json, and the gauntlet's 11-floor SHAPE becomes one fixed line map (gauntlet11.json); this is good for generated acts. It has the best goal-2 lever of the four: the fight backend is a slot (engine fights, logged fights, a learned SurrogateFights predictor). It also correctly names the choosers' trial fights, not the simulator, as the real CPU cost. Honest information is good: a view/world split, outcomes rolled when they become visible, and a leak test. Penalties under this lens: content is split between two loaders. Relics' combat side is read by Rust and their run side by Python, and the wording check is a mirrored Python test instead of element_names(). So one pack entry is validated twice, in two places, and a Rust planner or the explorer cannot reach the run vocabulary. | Two content loaders (Python for run content, Rust for combat), which weakens the single-registry rule that goal 1 rests on. |
| abstract-first | 6.5 | Content as data: events, relic run keys, a shop item pool where a custom item is one row, Neow pools, and per-group reward tables that a custom act can name. It also adds a run_effect group to element_names(), so its words are checked the same way as combat content, which is better than thin-shared on that point. 'The gauntlet as an act' file and the 'Observed' chance source (the bridge runs the same code, with the outcome the game showed) are good ideas. Goal 2 is strong: three ways to settle a fight (two turns deep, one turn deep, a value-net estimate) allow roughly 30k to 100k runs an hour, checked afterwards on paired two-turn runs. Weaknesses: the interpreter is in Python, separate from the Rust registry (the same split as thin-shared). The statistical-first fidelity plan lets small rule errors through that a decision would notice. Match and Keep becomes an outcome distribution under a fixed policy rather than a decision, which goes against the closed-vocabulary rule for content that people will want to play. |  |

Grafts:

- From thin-shared and abstract-first, a fight-settling slot behind play(specs): engine fights two turns deep, one turn deep, a value-net estimate at the fight's start (gauntlet value_parts/net_values), and later a learned (won, hp_end) surrogate. Learning runs use the cheap settlers; headline reads stay on paired two-turn engine fights. This is the main goal-2 lever, because the choosers' trial fights cost more than the run's own fights.
- From thin-shared and abstract-first, the map as data: generator parameters in a content file, plus the option of a fixed node list, with today's gauntlet SHAPE written as one such act (gauntlet11.json or gauntlet.json). Custom and generated acts then load the same way, and existing gauntlet reads stay comparable.
- From jar-oracle, choosers read an option's effect rows (for example 'Regret plus a random relic') instead of scoring the game's words. Run choosers then work on custom and generated events they have never seen.
- From jar-oracle, every oracle vector and every Rust chance call records how many calls each stream consumed, so a fight that draws on a run stream shows up instead of drifting silently.
- From abstract-first, an 'Observed' chance backend for the bridge: the live game's run advances through the same machine using the outcomes the game showed. This is a fourth backend next to GameStreams, Fast and Exact.
- From jar-oracle, enumerate which event comes from the eligible pool (about 15 to 25 outcomes) and the ? room type exactly. Set data-engine's per-site outcome cap K by measurement, not at 8, so these sites stay exact.
- From thin-shared, a 'support' check in log replay: the logged outcome must be among the outcomes the simulator lists with probability above 0. A plain item-by-item check like this carries over to custom content that has no jar original.
- Mitigation for data-engine's rebuild cost: a validator (a Python or `sts` call) that checks a pack's run rows against the atom list without a rebuild, so generated content can be tried quickly; only a new atom needs a Rust build.

Recommendation: Build data-engine. Under the goal-fit lens it is the only design where run content lives in the same registry, loader, pools and wording check as combat content. That is what goal 1 (weight 0.8) needs: a custom or generated event, relic run hook, Neow option or shop rule is a pack entry that loads exactly like an official one, and the explorer and Rust planners can reach it. It also keeps information honest by construction (no RNG in RunState, a resampled Hidden for planners, a leak test) and reuses rng.rs enumerate() for exact averaging.

Add these to it. First, thin-shared's and abstract-first's fight-settling slot (value-net estimate and a later surrogate for learning runs, paired two-turn checks for headline reads), so that goal 2 does not stall on the cost of choosers' trial fights. Second, the map and gauntlet as act data. Third, jar-oracle's rule that choosers read an option's effect rows, and its per-stream call counts. Fourth, set the Exact backend's outcome cap by measurement, so the event drawn from the pool and the ? room type stay exact.

Use jar-oracle's headless jar harness only as a fidelity tool for official items, not as part of the design. Fold the R2 draft's step 3 (docs/specs/run-layer-relics.md) into data-engine's vocabulary step before either is built, so the run vocabulary exists once. Keep the backlog-83 order: the decision maker comes after the content.

### Cost and code: how many steps a coding agent can land and check, how many lines must be kept in step, how much logic is duplicated between the simulator and the bridge, CPU and memory per run, dev-machine limits, and dependencies (JVM, Java 8)

Ranking: thin-shared, abstract-first, data-engine, jar-oracle

| Design | Score | Reasons | Fatal flaw |
|---|---|---|---|
| thin-shared | 8 | It reaches a measurable result soonest of the seed-exact designs. The first probe is jrandom.py plus map.py checked against every logged map, using only a 20-line Java class for the Random check. The second step is a rules port that must give 0 mismatches against log.txt and decisions.jsonl, so it can be checked in a session with no CPU cost. Because it is Python, adding an event or table needs no maturin build and no .pyd rename-and-swap, and it never touches pinned jobs or the job runner. That matters on this project (see the AGENTS.md gotcha and the memory note that unswapped landings must stay loadable). It deletes duplicated code: Bridge.card_pick's hand copy of the sim chooser and real_game_run.py's rules both move into one policy.py. It aims for seed-exact only where that is cheap (map, monster list, Neow, ? rolls) and falls back to distribution checks elsewhere, which is the smallest honest fidelity plan. It is the only design besides abstract-first that names the real cost driver, the choosers' trial fights (200-700 thread-seconds a run). It gives that cost a slot, the FightBackend, with a surrogate behind it. It also correctly finds that the logs hold no SHOP_SCREEN states (52 SHOP_ROOM, 0 shop screens). Costs: a second content loader (Python) next to registry.rs, and test_run_wording.py duplicating engine/tests/wording.rs. Rust search can't call it, though nothing needs that yet. |  |
| abstract-first | 7 | It is the smallest and fastest to start. logstats.py takes about half a day, and only about 20 lines of Rust go into registry::element_names(), so engine/tests/wording.rs stays the one word check. That is cheaper than thin-shared's separate Python wording test. The Observed chance source for the bridge is the leanest way to share one interpreter. Recasting the gauntlet as an act file (gauntlet.json) keeps old reads comparable without a second simulator. It also plans to settle fights by the value-net estimate, with a check against played fights. Its weakness under this lens: a statistical check against 70 runs is a weak check per line of code. Single events get 5-30 sightings, enough to catch only gross errors. A seed-exact map or reward replay gives a yes/no per screen at the same code cost. By putting exactness off until a decision measurably changes, it gives up the cheapest strong test there is. It also claims the map uses java.util.Random. That is wrong: it uses the game's Random on mapRng, which the other designs have right. |  |
| data-engine | 6 | Its architecture is the most coherent for goal 1: one Rust registry, one loader, and wording.rs covers everything. Its jjs (Nashorn in the game's own Java 8 JRE) oracle is a light dependency, and its cheapest probe, a headless jar map against 5 logged runs, is a good, cheap test. Under this lens it costs more. It is about 3,000 lines of Rust plus 1,500 of tests, and every content or logic change needs a maturin build, a .pyd swap and a check on pinned jobs. That slows each event-per-item loop and couples run work to the job queue. Three chance backends plus a Hidden resampler means more code than the honest-information need requires: rolling at reveal, as thin-shared and abstract-first do, removes Hidden for most streams. Its fidelity step 7 assumes logged shop screens, which don't exist. It gains nothing on CPU, since the run layer is a negligible share either way. Its strongest point is that Rust planners could call the run layer, and nothing needs that before backlog item 83. |  |
| jar-oracle | 4 | It carries the heaviest and riskiest dependency: a 600-900 line Java harness with HeadlessApplication, a Proxy GL20, faked textures and fonts, prefs, UnlockTracker and possibly shadow stubs. It also needs an estimated 10-40 s and 300-700 MB of JVM start-up per oracle run, and 10-50 MB of generated test data (vectors) to clean up. Doron Singer's weeks of work on a headless game show how this can drag on. Its first step blocks everything else on that probe succeeding. On top of the oracle it builds the same 2.5-3.5k lines of Rust as data-engine, with the same rebuild-and-swap cost. Its dependency scan is useful, and so is its idea of recording each stream's call count in every test vector. But the oracle tier buys little that log replay plus a Java class for Random alone doesn't already give. | Every per-item test and the first build step depend on a headless jar harness of unknown cost (static AbstractDungeon UI init, effectList ticking, fake GL). This is the opposite of the smallest path to a measurable result. |

Grafts:

- From abstract-first: list the run vocabulary in registry::element_names() (about 20 Rust lines) so engine/tests/wording.rs stays the single word check, and drop thin-shared's separate test_run_wording.py
- From abstract-first: run logstats.py as a half-day step zero next to the map probe. It is cheap, and it backs up the parts that are only distribution-exact
- From abstract-first: make the gauntlet a fixed-line act file (content/run/maps/gauntlet11.json, which thin-shared already names), with gauntlet.run() byte-identical as the first gate
- From abstract-first: an Observed chance source, so the bridge runs the same generators and the logged outcome is fed in rather than rolled
- From data-engine: the bridge runs a shadow simulator next to every live run and logs each mismatch as a fidelity bug. That gives about 30 runs a day of checking for almost no code
- From data-engine: its cheapest probe, run with the game's own jjs.exe (no compile step), as the way to check jrandom and the map against the jar
- From jar-oracle: record how many calls each RNG stream consumed at each screen in replay output, so any place a fight disturbs a run stream (potionRng, cardRng) is named instead of drifting silently
- From jar-oracle: the bridge reads an event option's data rows instead of scoring its words, which fixes the Golden Idol class of loss (run 52) as soon as events are data
- From thin-shared itself, moved earlier: the small bridge change that opens and logs the shop screen (bumping RUN_RULES), so shop checks get log data in parallel with the other steps

Recommendation: Build thin-shared: a Python package in scripts/run/, with content as rows in content/run/*.json and in the pack files' run keys, plus the grafts above. Two grafts matter most: list the run vocabulary in element_names() so one word check covers everything, and have the bridge shadow every live run with the simulator.

Under the cost-and-code lens it wins on four counts. It gives a yes/no result in one session at no CPU cost: jrandom plus the map against every logged seed, then the rules port with 0 mismatches. It avoids the maturin build and .pyd swap on every event or table added, a real recurring cost on this project. It removes two duplicated code paths (Bridge.card_pick's chooser copy and real_game_run.py's rules). And it puts the CPU lever where the CPU actually goes: the choosers' trial fights, through the FightBackend slot. CPU per simulated run does not separate the designs. Keep the vocabulary strictly as data, so a later Rust port (if a fast fight surrogate ever makes Python the limit) is a mechanical rewrite rather than a redesign. That port is the only reason data-engine's Rust-first layout would pay off, and nothing needs it before backlog item 83.

Mismatches with the brief and the designs:
- The logs hold 52 SHOP_ROOM states and no SHOP_SCREEN, so the shop log checks in data-engine and jar-oracle cannot run until the bridge opens shops.
- abstract-first says the map uses java.util.Random. It actually uses the game's Random on mapRng.

Before anyone builds, the manager must settle with the session writing the R2 draft (docs/specs/run-layer-relics.md) that R2's run state and vocabulary land in scripts/run/ (thin-shared step 3), not inside gauntlet.run(). Otherwise the vocabulary gets built twice.

### RISK (adversarial): fidelity gaps that bias learned decisions, unchecked feasibility claims, hidden-information leaks, rework for Acts 2-4 or a second character, and conflicts with work in flight

Ranking: thin-shared, data-engine, abstract-first, jar-oracle

| Design | Score | Reasons | Fatal flaw |
|---|---|---|---|
| thin-shared | 7 | It carries the least unchecked risk. Its log facts are correct: 90 seeds, no SHOP_SCREEN, about 34 events. From the jar it needs only Random, which uses nothing but gdx's RandomXS128 and so runs headless for sure. It demands seed-exactness only where that is cheap (map, boss, monster list, Neow, ? rolls) and falls back to matching the distribution elsewhere. It sees that the bridge must open shops (a RUN_RULES bump) before shop prices can be checked. It fits the R2 draft, which is already Python, and needs no .pyd rebuild or swap per new atom, which avoids the AGENTS.md lock and pinned-job friction. It spots the real CPU driver: the choosers' trial fights, not the run layer. Risks: (a) 'Rust 0-50 lines' is wrong. The Rust registry rejects unknown keys, so a `run` key on act1-relics.json needs Rust to accept it, and two loaders then parse the same pack file. (b) A second Python copy of rng.rs enumerate() has to be kept in step with the Rust one. (c) Step 2 ports the live rules to RunView before any content exists. The 0-mismatch replay guards it, but it is a live-behaviour change made early. (d) Rust search can never call the run vocabulary. That is low risk today, because backlog 83's leaf values gold and max HP through the net, not through run code. |  |
| data-engine | 6 | It is the strongest on goal 1: one Rust registry, run content parsed next to combat content, and wording.rs covering it. It has a good leak test (equal obs, different seeds, identical run_outcomes) and the live shadow-run idea. Risks it underrates: (a) Its fidelity plan checks shop stock against the logs, but there are no shop screens in them. (b) It treats card, potion and colorless rolls as seed-exact as long as combat leaves the streams alone. In fact the colorless shuffle reads shuffleRng, which combat consumes every floor (line 1150), and potionRng is used inside combat. CommunicationMod logs no stream counters, so the 'resync a counter from logged rewards' fix is guesswork and the replay chains will break early. (c) The Hidden struct plus Hidden::resample is code that can only go wrong. Rolling at reveal gives the same distribution, because the monster list is generated in order and the player sees a prefix of it, and a shuffled relic pool popped from the front is a uniform draw without replacement. One subtlety remains: canSpawn re-draws lose relics. (d) It takes over R2's vocabulary in Rust while R2 is an owner-facing draft planned in Python, a direct clash with work in flight. (e) It has the largest Rust surface (about 3k lines), and every new atom needs a .pyd rebuild and swap. (f) Seed-exact GameStreams only means anything for vanilla content. A custom card or relic in a pool changes the pool order, so the code that buys parity buys nothing for goal 1. |  |
| abstract-first | 5.5 | Its feasibility risk is lowest: a half-day logstats probe, and a 'make it seed-exact only where a decision changes' rule that stops chasing RNG. It turns the gauntlet into a degenerate act file and keeps the paired reads comparable. Risks: (a) Checking fidelity by statistics against thin logs can't catch the small rule errors that decisions exploit, such as duplicate exclusion, the offset reset on a rare, or elite tables. It admits this, but its main check is still chi-square against 5-30 sightings per event. (b) It is wrong that the map uses java.util.Random: mapRng is the game's own Random seeded with seed+act. (c) It replaces Match and Keep, the most-logged event (65 states), with an outcome distribution under a fixed policy, which biases how ? rooms are valued unless that policy matches the bot's. (d) It keeps the same Python two-loader issue with the `run` key, and its '20 lines of Rust' claim is too low for the same reason. (e) Its value-net fight settlement is a proxy that direction.md warns about. It does guard this with two-turn paired checks. |  |
| jar-oracle | 4.5 | Its dependency analysis is the best. It is right that static singletons rule out the jar at sim time, and right that the jar can only roll, never list outcomes. It also records per-stream RNG consumption. But its whole fidelity tier rests on the most unchecked claim: running event buttonEffect headless by reflection, ticking effectList under a no-op GL20 proxy, with AbstractDungeon's static block building TopPanel and the screens. No probe has run: the src2 stubs exist but have no output, and prior art spent weeks aligning a headless game. 600-900 lines of Java plus shadow stubs are a third codebase to keep in step, which works against 'streamline'. Unlock and profile state must match the owner's profile, or the vectors disagree with the logs. Its log replay also lists SHOP screens, which the logs don't have. It is honest about the R2 clash and the owner's order, but its step 1 is a gate whose failure removes the design's main advantage. | Its main check (per-event oracle vectors from the jar) depends on headless execution of event and effect classes that the game builds around UI singletons. Nothing has tested it, and if it fails the design falls back to what thin-shared already gets more cheaply. |

Grafts:

- From data-engine: a live shadow simulator alongside every bridge run, logging the first mismatch as a fidelity bug (about 30 checks a day at no extra game time). Also its leak test: equal observation, different seeds, identical outcome lists and policy picks.
- From data-engine: an arity cap plus a total-branch cap on exact enumeration, both tuned by measurement.
- From abstract-first: run logstats first (half a day; dedupe screen states into visits, Act 1 only). Adopt its rule: a stream becomes seed-exact only when that is cheap to test or a paired read shows a decision changing.
- From abstract-first: the gauntlet's 11-room SHAPE as a fixed line map file, so old reads replay byte-identical.
- From jar-oracle: record how many calls each stream takes per procedure. Treat paths the game doesn't seed (transformCard's new Random(), the global Collections.shuffle at AbstractDungeon.java:1170) as distribution tests only. Keep the jar and the decompiled source out of git.
- New from this review: mark shuffleRng-dependent rolls (colorless pool, line 1150) and every potionRng roll after a fight as distribution-only in log replay. Combat consumes these streams and CommunicationMod logs no counters, so the replay must not count them as seed-exact misses.
- New: decide now where the `run` key lives. The Rust registry rejects unknown keys, so either Rust learns to parse the `run` key or the run rows go in a separate content/run file. Settle this with the R2 session and the manager before either is built, so the vocabulary exists once.
- New: drop a pre-rolled Hidden struct in the simulator. Rolling at reveal gives the same distribution for the monster and elite lists and the relic pools, including the lost-relic rule when canSpawn forces a re-draw. Only a seed-exact replay mode needs stream state.

Recommendation: Build thin-shared, with the grafts. Under the risk lens it is the only design whose foundation is checkable today without the headless jar: the game's Random needs only RandomXS128, and 90 logged seeds with maps already exist. It does not promise shop or event parity that the logs can't back, and it lands where the R2 draft already plans to go (Python, the gauntlet's run state), so the work in flight isn't rewritten. Three things to correct first. (1) Budget a small Rust registry change, or a separate content/run file, for the `run` rows, because the registry rejects unknown keys. (2) Write down a trigger for moving the interpreter to Rust behind the same data: when fights are settled by the value-net estimate and the Python run layer passes about 10% of a run's CPU. (3) Add the bridge change that opens and logs shop screens early (a RUN_RULES bump), since shops are the main fidelity hole. Probe: run jrandom.py and map.py against all 90 logged seeds' maps, and logstats in parallel (one session, no CPU to speak of). Separately, spend an hour on a jjs call to MapGenerator only. It is the cheapest test of whether the jar runs headless for later test vectors, and nothing in the plan depends on it. Keep the owner's order: content and the simulator first, the decision maker after (backlog 83, direction.md 'Avoid').

