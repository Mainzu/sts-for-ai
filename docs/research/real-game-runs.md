# Real Slay the Spire runs played by the AI (2026-11-14)

On 2026-11-14 the AI played whole Ironclad runs (Ascension 0) in the real game, through the real-game bridge
(`docs/specs/real-game-bridge.md`, README "Real-game bridge"). Nobody touched the game while it played.

How it plays:

- **Fights** are played by the engine: each game state is rebuilt as an engine fight (`Combat.from_view`), and the
  product's search (depth_paired's policy, two turns deep with the value net
  `runs/2026-11-10-packnet40k-s201-r1-91c8ae0/model.pt@hpe0.01`) picks the actions.
- **Fidelity check:** before each action without chance in it (no draw, no random target), the engine predicts the
  game's next state. "Steps matched" counts the predictions the game then agreed with, field by field.
- **Fallback:** a fight the engine can't model (a monster or card it doesn't load) is finished by a simple rule player
  (`real_game_run.fallback_command`). The engine models Act 1 only, so every Act 2 fight is a fallback fight.
- **Outside fights** (map, Neow and events, card rewards, rest sites, shops) follow `scripts/real_game_run.py`'s fixed
  rules; card rewards are picked by the sim chooser (one-turn trial fights with the same net).

The tables below are written by `python scripts/real_game_report.py --write` from the records in
`results/real-game/<stamp>/` (gitignored). The notes after them are written by hand. A fight's HP reads
"start -> end (after)": end is the HP when the fight ended, before end-of-fight relics; after is the HP the run carries
on with, once Burning Blood has healed 6.

Fidelity counts only steps without chance: the controller compares the engine's prediction with the game's next
state when every sample agrees. A monster turn whose outcome involves chance (a random target, a rolled move) is
never compared, so a fight's "matched" count says nothing about those turns. Run 83, turns 2-3: Flame Barrier was up
while a Shield Gremlin's Protect shielded the Mad Gremlin in slot 2; the game showed it at 21 HP with 7 block, the
engine 17 HP with 11 block, and the fight still counted 202 of 202 matched. So the fidelity percentages below cover
chance-free steps only; checking chance steps against the outcome the game showed is backlog 86.

Settings: the summary has one table per ascension level and run-layer rules version (`real_game_run.RUN_RULES`;
version 2, from 8d7d529a, takes a rest site first below half HP; version 3 adds the map's look-ahead, version 4 whole-word event matching and version 5 elites last again, all
below). Run-layer changes before the version existed are
not versioned: the boss relic skips Runic Dome from run 8 on, and a potion's card choice takes a card the engine
loads from run 31 on (both in "Bugs the live runs found").

Run rules 3 (from 2026-11-14 17:06): the map judges each next node by the paths below it up to the next rest site. A
hallway fight counts 15 HP and an elite 40 (about the 90th and the 75th to 90th percentiles of HP lost in the A20
records, after Burning Blood's heal); a path survives when those costs add up to less than the HP now. The node whose
best path survives with the most card picks wins (an elite counts as two), else the node whose cheapest path costs
least; below half HP a rest site next still comes first. On runs 37's and 49's maps it takes the branch those runs
didn't (`test_map_looks_ahead_to_the_next_rest_site`). It takes fewer fights and elites on risky paths, so it gives up
card picks and relics. What those lost picks cost at the boss isn't measured (the gauntlet has no map); only the runs'
results will show whether the trade pays.

Run rules 4 (from 2026-11-14 17:25): event options are scored on whole words (with an s, d, ed or number ending), and
"trap" is a bad word. Run 52 took the Golden Idol because "golden" scored as gold and "[Take]" slipped past the bad
word "take ", and the idol's trap cost 8 max HP; the event is now left alone (`test_event_leaves_the_golden_idol`).
Replayed over the 128 event screens in the records, only the Golden Idol and two Match and Keep picks change (the old
rule picked "Cleave" because it holds "leave"). Later run-layer findings are noted here and batched.

Run rules 5 (from 2026-11-14 17:47): elites go last again. Rules 3 and 4 counted an elite as two card picks, so the
look-ahead took four elites by choice at A20 (runs 53-55), costing 51, 35, 0 and 73 HP; the last was run 55, which
took three Sentries over a rest site at 73 of 75 HP and died, and run 52 died to Gremlin Nob taken as the cheapest
path when no path survived. Now an elite is taken only when every next node is one, and elites on a path count no
card pick (they still count their HP cost), as the simulator measured (an elite costs more HP than it pays). The rest
of the look-ahead and the event words stay as in rules 4 (`test_map_takes_an_elite_only_when_every_node_is_one`).
From the same time the game stays open after a death: the next run starts at the main menu, and the game is closed
only at the Act 2 stop (CommunicationMod can't abandon a run) or when the loop stops.

Fight guard 1 (from 2026-11-14 18:02): from this time on the bridge's fighter differs from the product's search in one
way: whenever an option wins the fight at once, it plays the best such option. The search passed such wins when the
net's score for carrying on beat a finished win at the same HP, which happens once a fight has cost a lot of HP: run 56
left a Blue Slaver at 6 HP from turn 8 to 18 (23 -> 5 HP), and run 52's floor-5 gremlins took it from 79 to 22. Over
the day's records 120 of 2983 decisions had a winning option not taken (most of them ties; backlog 82 names the strict
cases and the engine fix). The guard catches the killing blow only, not a kill that needs two cards
(`test_guard_takes_the_win_the_search_passed`, on runs 56's and 52's recorded decisions). The summary keeps runs with
and without the guard apart.

End of the day (2026-11-14; the loop stopped at 22:00, after run 90). Per setting, Act 1 bosses beaten of runs
played: A0 rules 1, 22 of 27; A20 rules 1, 3 of 7; A20 rules 2, 7 of 16; A20 rules 3, 1 of 3; A20 rules 4, 0 of 3;
A20 rules 5 without the fight guard, 1 of 1; A20 rules 5 with fight guard 1, 18 of 33 (55%, about 9 points either
way; rules 2's 44% is about 12 points either way, so the two aren't told apart yet). In that last setting the 15 runs
that lost died at the boss 10 times (Hexaghost 8, Slime Boss 1, The Guardian 1) and before it 5 times (runs 72, 76,
78, 79 and 83: forced elites, a rest site that upgraded at exactly 60% HP before two elites, the power-cap fallback
and the Shield Gremlin stall). Per boss in that setting: Slime Boss 10 of 11, The Guardian 7 of 8, Hexaghost 1 of 9.
Fidelity there: 3777 of 3782 chance-free steps (99.9%; chance steps aren't compared, see above). Not fixed and open:
the items under "Not fixed" below (a turn-only free Defend), backlog 82 (leaf-beats-win), 85 (stalls) and 86 (chance-step fidelity), and the
batched run-layer finding (rest by the path ahead, run 72).

<!-- GENERATED by scripts/real_game_report.py: don't edit by hand -->

Updated 2026-11-15 01:25 from 69 record folders.

## Summary

One table per setting (ascension, the run layer's rules version and the fight guard): settings' numbers are never pooled.

### Ascension 0, run rules 1 (fights before rest sites at any HP)

| | |
|---|---|
| Runs | 27 (25 finished, 6 of them stopped when Act 2 started) |
| Act 1 bosses beaten | 22 |
| Fights | 332 (314 won), 267 played by the engine to the end |
| Fidelity | 3291 of 3321 chance-free steps matched the game (99.1%; steps with chance aren't compared) |
| Decision time | median 0.3 s, worst 110.7 s (floor 11, FuzzyLouseNormal + FuzzyLouseNormal + FuzzyLouseNormal) over 1737 decisions |

### Ascension 20, run rules 1 (fights before rest sites at any HP)

| | |
|---|---|
| Runs | 7 (7 finished, 3 of them stopped when Act 2 started) |
| Act 1 bosses beaten | 3 |
| Fights | 60 (56 won), 59 played by the engine to the end |
| Fidelity | 748 of 751 chance-free steps matched the game (99.6%; steps with chance aren't compared) |
| Decision time | median 0.2 s, worst 46.0 s (floor 13, JawWorm + SpikeSlime_M) over 333 decisions |

### Ascension 20, run rules 2 (below half HP a rest site first (8d7d529a))

| | |
|---|---|
| Runs | 16 (16 finished, 7 of them stopped when Act 2 started) |
| Act 1 bosses beaten | 7 |
| Fights | 154 (145 won), 154 played by the engine to the end |
| Fidelity | 1934 of 1936 chance-free steps matched the game (99.9%; steps with chance aren't compared) |
| Decision time | median 0.2 s, worst 96.1 s (floor 16, SlimeBoss) over 960 decisions |

### Ascension 20, run rules 3 (the map looks ahead to the next rest site)

| | |
|---|---|
| Runs | 3 (3 finished, 1 of them stopped when Act 2 started) |
| Act 1 bosses beaten | 1 |
| Fights | 23 (21 won), 23 played by the engine to the end |
| Fidelity | 337 of 337 chance-free steps matched the game (100.0%; steps with chance aren't compared) |
| Decision time | median 0.1 s, worst 14.4 s (floor 14, AcidSlime_L) over 130 decisions |

### Ascension 20, run rules 4 (rules 3, and event words match whole words)

| | |
|---|---|
| Runs | 3 (3 finished, 0 of them stopped when Act 2 started) |
| Act 1 bosses beaten | 0 |
| Fights | 24 (21 won), 24 played by the engine to the end |
| Fidelity | 315 of 316 chance-free steps matched the game (99.7%; steps with chance aren't compared) |
| Decision time | median 0.2 s, worst 35.8 s (floor 16, SlimeBoss) over 181 decisions |

### Ascension 20, run rules 5 (rules 4, and elites last again)

| | |
|---|---|
| Runs | 1 (1 finished, 1 of them stopped when Act 2 started) |
| Act 1 bosses beaten | 1 |
| Fights | 10 (10 won), 10 played by the engine to the end |
| Fidelity | 119 of 119 chance-free steps matched the game (100.0%; steps with chance aren't compared) |
| Decision time | median 0.2 s, worst 91.2 s (floor 16, SlimeBoss) over 45 decisions |

### Ascension 20, run rules 5 (rules 4, and elites last again), fight guard: a winning option the search passed is taken

| | |
|---|---|
| Runs | 33 (33 finished, 18 of them stopped when Act 2 started) |
| Act 1 bosses beaten | 18 |
| Fights | 311 (296 won), 309 played by the engine to the end |
| Fidelity | 3777 of 3782 chance-free steps matched the game (99.9%; steps with chance aren't compared) |
| Decision time | median 0.1 s, worst 78.8 s (floor 16, SlimeBoss) over 1930 decisions |

## Runs

### Run 1

- Seed 5185322666284402695, started 06:05 (record folder `20261114-060511`).
- Ascension 0, run rules 1. Reached floor 22 (act 2); died on floor 22 to Centurion + Healer (score 184).
- Act 1 boss: The Guardian, beaten, HP 71 -> 44 (50 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 77 (80), F2 74 (80), F3 74 (80), F4 76 (80), F7 73 (79), F10 74 (80), F11 75 (80), F12 80, F13 72 (78), F14 65 (71), F16 44 (50).
- Deck at the end (22): Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Swift Strike+, True Grit+, Clothesline, Pommel Strike, Pommel Strike, Rampage, Shockwave, Perfected Strike, Havoc, Havoc, Intimidate, Fire Breathing+.
- Relics at the end: Burning Blood, Ornamental Fan, Runic Pyramid.

### Run 2

- Seed 5117223751276531401, started 06:28 (record folder `20261114-062806`).
- Ascension 0, run rules 1. Reached floor 27 (act 2); died on floor 27 to Centurion + Healer (score 256).
- Act 1 boss: The Guardian, beaten, HP 83 -> 61 (67 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 85 (88), F2 82 (88), F3 80 (86), F4 86 (88), F6 49 (55), F7 50 (56), F8 46 (52), F11 76 (82), F12 79 (85), F13 84 (88), F14 77 (83), F16 61 (67).
- Deck at the end (23): Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Havoc, Iron Wave, Demon Form, Metallicize, Armaments, Armaments, Clothesline, Anger, Disarm, Uppercut, Whirlwind, Pummel, Perfected Strike.
- Relics at the end: Burning Blood, Bottled Flame, Tiny Chest, Ancient Tea Set, Runic Dome, Pear.

### Run 3

- Seed 3630205366522552790, started 06:47 (record folder `20261114-062806`).
- Ascension 0, run rules 1. Reached floor 2 (act 1); stopped by a game restart on floor 2 (the run was left).
- Act 1 boss: The Guardian.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 71 (77), F2 77 (80).
- Deck at the end (12): Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash, Ghostly Armor, Spot Weakness.
- Relics at the end: Burning Blood, Art of War.

### Run 4

- Seed 8116708074135674648, started 06:49 (record folder `20261114-064924`).
- Ascension 0, run rules 1. Reached floor 23 (act 2); died on floor 23 to Sentry + SphericGuardian (score 217).
- Act 1 boss: Slime Boss, beaten, HP 70 -> 69 (74 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 73 (79), F2 68 (74), F3 74 (80), F5 53 (59), F7 36 (42), F8 37 (43), F10 33 (39), F11 39 (45), F12 37 (43), F13 31 (37), F14 30 (36), F16 69 (74).
- Deck at the end (23): Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Dropkick, Evolve, Anger, Thunderclap, Wild Strike, Anger, Thunderclap, Exhume, Thunderclap, Dropkick, CurseOfTheBell, Cleave, Clothesline.
- Relics at the end: Burning Blood, Golden Idol, Centennial Puzzle, Gremlin Horn, Du-Vu Doll, Eternal Feather, Calling Bell, Pen Nib, Letter Opener, CaptainsWheel.

### Run 5

- Seed -8496598383590318938, started 07:14 (record folder `20261114-064924`).
- Ascension 0, run rules 1. Reached floor 4 (act 1); stopped by a game restart on floor 4 (the run was left).
- Act 1 boss: Slime Boss.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 74 (80), F3 74 (80).
- Deck at the end (12): Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash, Headbutt, Infernal Blade.
- Relics at the end: Burning Blood.

### Run 6

- Seed -3858730473599923077, started 07:22 (record folder `20261114-072137`).
- Ascension 0, run rules 1. Reached floor 21 (act 2); died on floor 21 to Cultist + Cultist + Cultist (score 179).
- Act 1 boss: The Guardian, beaten, HP 80 -> 43 (49 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 77 (80), F2 74 (80), F3 77 (80), F4 76 (80), F5 76 (80), F10 75 (80), F11 76 (80), F12 76 (80), F13 72 (78), F14 68 (74), F16 43 (49).
- Deck at the end (20): Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Perfected Strike+, Flame Barrier+, Hemokinesis, Twin Strike, Ghostly Armor, Twin Strike, Perfected Strike, Evolve, Double Tap, Warcry, Cleave.
- Relics at the end: Burning Blood, Eternal Feather, Runic Dome.

### Run 7

- Seed 3079942981753671445, started 07:28 (record folder `20261114-072137`).
- Ascension 0, run rules 1. Reached floor 23 (act 2); died on floor 23 to GremlinFat + GremlinThief + GremlinLeader (score 253).
- Act 1 boss: Slime Boss, beaten, HP 80 -> 80.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 76 (80), F2 76 (80), F3 80, F4 75 (80), F5 75 (80), F7 72 (78), F8 78 (80), F10 74 (80), F12 76 (80), F13 77 (80), F14 69 (75), F16 80.
- Deck at the end (21): Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Fire Breathing+, Pommel Strike, Iron Wave, Perfected Strike, Wild Strike, Evolve, Wild Strike, Heavy Blade, Reckless Charge, Intimidate, Heavy Blade+.
- Relics at the end: Burning Blood, Oddly Smooth Stone, Ancient Tea Set, Eternal Feather, Cursed Key.

### Run 8

- Seed 1100696453657088081, started 07:40 (record folder `20261114-074035`).
- Ascension 0, run rules 1. Reached floor 16 (act 1); died on floor 16 to TheGuardian (score 110).
- Act 1 boss: The Guardian, lost, HP 51 -> 0.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 75 (80), F2 79 (80), F4 78 (84), F8 53 (58), F10 27 (33), F11 26 (31), F12 20 (26), F16 0.
- Deck at the end (16): Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Anger+, True Grit, Combust, Armaments, Impervious, Heavy Blade, Clothesline.
- Relics at the end: Burning Blood, Bottled Lightning, CeramicFish, Singing Bowl, Letter Opener.

### Run 9

- Seed 3896601148687006601, started 07:48 (record folder `20261114-074750`).
- Ascension 0, run rules 1. Reached floor 31 (act 2); died on floor 31 to Cultist + Chosen (score 237).
- Act 1 boss: The Guardian, beaten, HP 80 -> 55 (61 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 77 (80), F2 74 (80), F3 76 (80), F4 77 (80), F5 62 (68), F8 60 (66), F10 66 (72), F11 72 (78), F13 76 (80), F14 75 (80), F16 55 (61).
- Deck at the end (19): Rampage+, Shockwave+, Shockwave+, Armaments+, Clash+, Armaments, True Grit, Flex, Whirlwind, Whirlwind, Immolate, Brutality, Entrench, Sword Boomerang, Inflame, Anger, Flame Barrier+, Headbutt, Reckless Charge+.
- Relics at the end: Burning Blood, Anchor, Pandora's Box, Pear.

### Run 10

- Seed -8575456542609944860, started 08:01 (record folder `20261114-074750`).
- Ascension 0, run rules 1. Reached floor 21 (act 2); died on floor 21 to Cultist + Chosen (score 239).
- Act 1 boss: Slime Boss, beaten, HP 62 -> 62 (68 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 74 (80), F3 80, F4 75 (80), F5 74 (80), F7 69 (75), F10 75 (80), F11 76 (80), F12 54 (60), F13 54 (60), F14 56 (62), F16 62 (68).
- Deck at the end (22): Bash+, Inflame+, Wild Strike+, Whirlwind+, Rampage, Cleave, Anger, Thunderclap, Perfected Strike, Cleave, Feed, Pommel Strike, Twin Strike, Brutality, Corruption, Inflame, Cleave, Wild Strike, Dark Embrace, Fiend Fire, Rage, Shrug It Off.
- Relics at the end: Burning Blood, Question Card, Orichalcum, Pandora's Box.

### Run 11

- Seed 2432447239032735212, started 08:10 (record folder `20261114-080956`).
- Ascension 0, run rules 1. Reached floor 21 (act 2); died on floor 21 to Shelled Parasite + FungiBeast (score 183).
- Act 1 boss: Slime Boss, beaten, HP 74 -> 39 (57 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 80, F3 80, F4 79 (80), F5 75 (80), F6 63 (69), F8 60 (66), F11 64 (70), F13 68 (74), F16 39 (57).
- Deck at the end (19): Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Dramatic Entrance+, Perfected Strike, Thunderclap, Carnage, Fire Breathing, Hemokinesis, Reckless Charge, Infernal Blade, Metallicize, Armaments, Sword Boomerang.
- Relics at the end: Burning Blood, Meat on the Bone, Red Skull, Odd Mushroom, Empty Cage.

### Run 12

- Seed -7614463831272527574, started 08:18 (record folder `20261114-081755`).
- Ascension 0, run rules 1. Reached floor 22 (act 2); died on floor 22 to Cultist + Chosen (score 240).
- Act 1 boss: Slime Boss, beaten, HP 85 -> 81 (85 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 78 (80), F3 82 (85), F4 82 (85), F5 83 (85), F11 73 (79), F12 72 (78), F13 75 (81), F14 84 (85), F16 81 (85).
- Deck at the end (18): Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Blood for Blood+, Combust+, Blood for Blood, Rupture, Wild Strike, Clash, Double Tap, Immolate, Clothesline, Shrug It Off+.
- Relics at the end: Burning Blood, Art of War, White Beast Statue, Ornamental Fan, Runic Cube.

### Run 13

- Seed 3149377138785705620, started 08:30 (record folder `20261114-082949`).
- Ascension 0, run rules 1. Reached floor 21 (act 2); died on floor 21 to Chosen (score 185).
- Act 1 boss: The Guardian, beaten, HP 64 -> 40 (46 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 73 (79), F2 77 (80), F3 79 (80), F5 75 (80), F6 13 (19), F10 30 (36), F11 23 (29), F12 29 (35), F13 33 (39), F14 34 (40), F16 40 (46).
- Deck at the end (20): Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash, Clash, Rage, Impervious, Anger, Perfected Strike, Clothesline, Metallicize, Armaments, Warcry, Clash, Reaper.
- Relics at the end: Black Blood, Turnip, Sundial.

### Run 14

- Seed -7626674956788279366, started 08:42 (record folder `20261114-084142`).
- Ascension 0, run rules 1. Reached floor 22 (act 2); died on floor 22 to Centurion + Healer (score 194).
- Act 1 boss: The Guardian, beaten, HP 70 -> 34 (39 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 74 (80), F2 70 (76), F3 71 (77), F4 69 (75), F5 72 (78), F6 80, F7 70 (76), F8 30 (36), F11 36 (42), F14 64 (70), F16 34 (39).
- Deck at the end (20): Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Shrug It Off, Blood for Blood, Shrug It Off, Clash, Disarm, Perfected Strike, Carnage, Berserk, Pommel Strike, Anger.
- Relics at the end: Black Blood, Art of War, Bag of Marbles, Red Skull.

### Run 15

- Seed 85827907834628974, started 08:55 (record folder `20261114-085507`).
- Ascension 0, run rules 1. Reached floor 20 (act 2); died on floor 20 to Centurion + Healer (score 172).
- Act 1 boss: The Guardian, beaten, HP 80 -> 45 (48 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 75 (80), F2 77 (80), F5 79 (80), F7 78 (80), F8 80, F11 73 (79), F12 73 (79), F13 79 (80), F14 79 (80), F16 45 (48).
- Deck at the end (19): Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Warcry+, Anger+, Shrug It Off, Armaments, Cleave, Carnage, Thunderclap, Immolate, Disarm, Warcry.
- Relics at the end: Burning Blood, Vajra, Singing Bowl, SacredBark.

### Run 16

- Seed 6135501573089124404, started 09:07 (record folder `20261114-090728`).
- Ascension 0, run rules 1. Reached floor 16 (act 1); died on floor 16 to TheGuardian (score 156).
- Act 1 boss: The Guardian, lost, HP 83 -> 0.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 77 (80), F2 79 (80), F3 77 (80), F4 74 (80), F5 74 (80), F7 70 (76), F8 62 (68), F11 68 (74), F14 77 (83), F16 0.
- Deck at the end (18): Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Blood for Blood+, Rampage+, Disarm, Clothesline, Thunderclap, Feed, Power Through, Shrug It Off, Rampage.
- Relics at the end: Burning Blood, Ancient Tea Set, PreservedInsect.

### Run 17

- Seed 5666068999316377336, started 09:13 (record folder `20261114-090728`).
- Ascension 0, run rules 1. Reached floor 21 (act 2); died on floor 21 to SnakePlant (score 189).
- Act 1 boss: Hexaghost, beaten, HP 52 -> 27 (33 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 80, F2 74 (80), F3 74 (80), F4 70 (76), F6 16 (22), F7 17 (23), F8 22 (28), F11 24 (30), F12 16 (22), F13 22 (28), F14 22 (28), F16 27 (33).
- Deck at the end (22): Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash, Twin Strike, Twin Strike, Searing Blow, Metallicize+, Flex, Rampage, Power Through, Evolve+, Shrug It Off, Feed, Ghostly Armor+, Headbutt+.
- Relics at the end: Burning Blood, Frozen Egg 2, Bronze Scales, Runic Pyramid.

### Run 18

- Seed 3453456897329479086, started 11:24 (record folder `20261114-112420`).
- Ascension 0, run rules 1. Reached floor 18 (act 2); died on floor 18 to Byrd + Byrd + Byrd (score 170).
- Act 1 boss: The Guardian, beaten, HP 78 -> 47 (53 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 73 (79), F2 79 (80), F4 74 (80), F5 67 (73), F6 42 (48), F7 43 (49), F8 40 (46), F10 44 (50), F11 36 (42), F12 42 (48), F13 48 (54), F16 47 (53).
- Deck at the end (17): Strike, Strike, Strike, Strike, Defend, Defend, Defend+, Defend+, Bash, Feel No Pain, Pommel Strike, Demon Form, Clothesline, True Grit, Perfected Strike, Inflame, Impervious.
- Relics at the end: Burning Blood, War Paint, PreservedInsect, SlaversCollar.

### Run 19

- Seed -6793482581188505843, started 11:36 (record folder `20261114-112420`).
- Ascension 0, run rules 1. Reached floor 21 (act 2); died on floor 21 to Centurion + Healer (score 175).
- Act 1 boss: Hexaghost, beaten, HP 72 -> 7 (13 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 80, F3 74 (80), F4 75 (80), F5 69 (75), F7 67 (73), F8 66 (72), F12 60 (66), F14 66 (72), F16 7 (13).
- Deck at the end (19): Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Rampage+, Flame Barrier+, Evolve, Fire Breathing, Pommel Strike, Wild Strike, Rage, Brutality, Havoc+, Intimidate+.
- Relics at the end: Burning Blood, MealTicket, Black Star, MutagenicStrength.

### Run 20

- Seed 4140320180162977119, started 11:42 (record folder `20261114-112420`).
- Ascension 0, run rules 1. Reached floor 21 (act 2); died on floor 21 to Sentry + SphericGuardian (score 181).
- Act 1 boss: The Guardian, beaten, HP 70 -> 62 (68 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 74 (80), F2 79 (80), F3 75 (80), F4 65 (71), F5 65 (71), F7 65 (71), F10 65 (71), F11 64 (70), F13 67 (73), F14 64 (70), F16 62 (68).
- Deck at the end (21): Strike, Strike, Strike, Strike, Strike+, Defend, Defend, Defend, Defend, Bash+, Trip+, Clothesline+, Anger, Carnage+, Disarm, Iron Wave, Iron Wave, Power Through, Disarm, Clothesline, Armaments.
- Relics at the end: Burning Blood, Whetstone, Velvet Choker.

### Run 21

- Seed 215491633072269124, started 11:53 (record folder `20261114-112420`).
- Ascension 0, run rules 1. Reached floor 19 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: Hexaghost, beaten, HP 78 -> 29 (35 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 82 (88), F2 86 (88), F3 83 (88), F6 62 (68), F7 56 (62), F8 65 (71), F10 39 (45), F11 42 (48), F12 43 (49), F14 56 (50), F16 29 (35).
- Deck at the end (19): Strike+, Strike, Strike, Strike+, Strike, Defend, Defend, Defend, Defend, Bash, Anger, Battle Trance, Anger, Perfected Strike, Clash, Armaments, Clothesline, Double Tap, Metallicize.
- Relics at the end: Burning Blood, Toy Ornithopter, Blood Vial, Whetstone, Black Star.

### Run 22

- Seed 7169971514925045095, started 12:04 (record folder `20261114-120336`).
- Ascension 0, run rules 1. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: The Guardian, beaten, HP 41 -> 29 (35 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 72 (78), F2 77 (80), F3 74 (80), F4 72 (78), F5 78 (80), F6 67 (73), F7 73 (79), F8 72 (78), F10 64 (70), F12 58 (64), F13 64 (70), F14 11 (17), F16 29 (35).
- Deck at the end (20): Strike, Strike, Strike, Strike, Strike, Defend+, Defend, Defend, Defend, Bash, Discovery, Cleave, Armaments+, Twin Strike, Demon Form, Shrug It Off, Fire Breathing, Intimidate, Shrug It Off, Spot Weakness.
- Relics at the end: Burning Blood, Bottled Flame, War Paint, Odd Mushroom, SlaversCollar.

### Run 23

- Seed -6750911003323032875, started 12:21 (record folder `20261114-122134`).
- Ascension 0, run rules 1. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: The Guardian, beaten, HP 68 -> 40 (58 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 72 (78), F3 77 (80), F4 79 (80), F5 74 (80), F6 66 (72), F7 63 (69), F8 59 (65), F11 61 (67), F12 62 (68), F13 62 (68), F16 40 (58).
- Deck at the end (20): Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Infernal Blade+, Anger+, Pommel Strike, Battle Trance, Battle Trance, Armaments, Clash, Shrug It Off, Disarm, Shrug It Off.
- Relics at the end: Burning Blood, Meat on the Bone, TungstenRod, Sozu.

### Run 24

- Seed 7041190601079165608, started 12:41 (record folder `20261114-124125`).
- Ascension 0, run rules 1. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: Slime Boss, beaten, HP 85 -> 53 (59 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 74 (80), F2 77 (80), F3 72 (78), F4 69 (75), F5 74 (80), F6 74 (80), F8 73 (79), F10 79 (85), F11 84 (85), F12 85, F13 83 (85), F14 84 (85), F16 53 (59).
- Deck at the end (20): Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Ghostly Armor, Spot Weakness, Spot Weakness, Cleave, Hemokinesis, Sword Boomerang, Iron Wave, Rupture, Whirlwind, Double Tap, Offering.
- Relics at the end: Burning Blood, Torii, WingedGreaves, Snecko Eye.

### Run 25

- Seed -1462794905055538043, started 12:54 (record folder `20261114-125346`).
- Ascension 0, run rules 1. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: The Guardian, beaten, HP 59 -> 46 (49 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 80, F2 72 (78), F3 78 (80), F4 73 (79), F5 76 (80), F7 76 (80), F8 75 (80), F12 69 (74), F13 65 (71), F14 53 (59), F16 46 (49).
- Deck at the end (20): Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Flex+, Perfected Strike+, Wild Strike, Shrug It Off, Anger, Battle Trance, Uppercut, Inflame+, Limit Break, Limit Break, Pummel.
- Relics at the end: Burning Blood, InkBottle, Golden Idol, Letter Opener, Tiny House.

### Run 26

- Seed -8160843563818962900, started 13:09 (record folder `20261114-130922`).
- Ascension 0, run rules 1. Reached floor 7 (act 1); died on floor 7 to GremlinThief + GremlinThief + GremlinWarrior + GremlinWizard (score 55).
- Act 1 boss: Slime Boss.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 74 (80), F2 74 (80), F3 80, F4 69 (75), F5 66 (72), F6 19 (25), F7 0.
- Deck at the end (15): Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash, Inflame, Dropkick, Infernal Blade, Pommel Strike, Demon Form.
- Relics at the end: Burning Blood, Old Coin.

### Run 27

- Seed 1575058980355282486, started 13:15 (record folder `20261114-131518`).
- Ascension 0, run rules 1. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: Slime Boss, beaten, HP 81 -> 82 (88 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 82 (88), F3 86 (88), F4 83 (88), F5 84 (88), F6 62 (68), F7 66 (72), F8 70 (76), F11 76 (82), F14 75 (81), F16 82 (88).
- Deck at the end (18): Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Infernal Blade+, Anger, Clash, Inflame, Shockwave, Clash, Thunderclap, Offering.
- Relics at the end: Black Blood, Blue Candle, Vajra.

### Run 28

- Seed -1365700698816375541, started 13:23 (record folder `20261114-132234`).
- Ascension 20, run rules 1. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: The Guardian, beaten, HP 87 -> 16 (18 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 73 (79), F4 77 (83), F5 81 (87), F6 43 (49), F10 69 (75), F11 68 (74), F12 49 (55), F13 47 (53), F14 53 (59), F16 16 (18).
- Deck at the end (17): AscendersBane, Strike, Strike, Defend, Defend, Defend, Defend, Bash, Anger, Bludgeon, Armaments, Shrug It Off, Rage, Heavy Blade, Rampage, Heavy Blade, Impervious.
- Relics at the end: Burning Blood, Regal Pillow, MawBank, Astrolabe.

### Run 29

- Seed -8001512894325499316, started 13:33 (record folder `20261114-133230`).
- Ascension 20, run rules 1. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: Hexaghost, beaten, HP 71 -> 14 (20 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 71 (77), F4 72 (78), F5 75 (81), F7 76 (82), F8 51 (44), F11 76 (82), F13 70 (74), F14 65 (71), F16 14 (20).
- Deck at the end (20): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend+, Defend, Defend, Defend+, Bash+, Armaments+, Flame Barrier+, Headbutt, Clash, Intimidate, Dropkick, Shockwave, Fire Breathing, Fiend Fire.
- Relics at the end: Burning Blood, War Paint, Bag of Preparation, Golden Idol, Fusion Hammer.

### Run 30

- Seed -3649630443815255028, started 13:43 (record folder `20261114-134302`).
- Ascension 20, run rules 1. Reached floor 7 (act 1); died on floor 7 to Lagavulin (score 90).
- Act 1 boss: The Guardian.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 68 (74), F3 65 (71), F4 71 (77), F5 65 (71), F6 38 (44), F7 0.
- Deck at the end (14): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash, Sword Boomerang, Wild Strike, Metallicize.
- Relics at the end: Burning Blood.

### Run 31

- Seed -1938650433671466484, started 13:50 (record folder `20261114-135010`).
- Ascension 20, run rules 1. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: Hexaghost, beaten, HP 73 -> 31 (37 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 64 (70), F3 60 (66), F4 66 (72), F5 72 (78), F7 74 (80), F11 65 (71), F12 71 (77), F13 61 (67), F14 67 (73), F16 31 (37).
- Deck at the end (17): AscendersBane, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Anger+, Anger, Metallicize, Clothesline, Rampage, Battle Trance, Thunderclap, Bludgeon.
- Relics at the end: Burning Blood, Prayer Wheel, Empty Cage.

### Run 32

- Seed 1531808256413671300, started 13:57 (record folder `20261114-135634`).
- Ascension 20, run rules 1. Reached floor 16 (act 1); died on floor 16 to SlimeBoss (score 200).
- Act 1 boss: Slime Boss, lost, HP 64 -> 0.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 71 (77), F4 63 (69), F5 63 (69), F6 24 (30), F10 34 (40), F14 58 (64), F16 0.
- Deck at the end (14): AscendersBane, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Perfected Strike, Infernal Blade, Clothesline, Blood for Blood.
- Relics at the end: Burning Blood, Vajra, Nunchaku.

### Run 33

- Seed -3270339441473894311, started 14:03 (record folder `20261114-140235`).
- Ascension 20, run rules 1. Reached floor 12 (act 1); died on floor 12 to SpikeSlime_L (score 164).
- Act 1 boss: The Guardian.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 56 (62), F2 60 (66), F3 60 (66), F4 44 (50), F8 8 (14), F10 6 (12), F11 4 (10), F12 0.
- Deck at the end (14): AscendersBane, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Spot Weakness+, Shrug It Off, Armaments, Thunderclap.
- Relics at the end: Burning Blood, Anchor, Regal Pillow.

### Run 34

- Seed 7376156113616818975, started 14:10 (record folder `20261114-140928`).
- Ascension 20, run rules 1. Reached floor 16 (act 1); died on floor 16 to SlimeBoss (score 208).
- Act 1 boss: Slime Boss, lost, HP 49 -> 0.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 68 (74), F2 71 (77), F3 70 (76), F5 58 (64), F7 39 (45), F11 32 (38), F12 27 (36), F13 3 (9), F14 4 (10), F16 0.
- Deck at the end (18): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Cleave, Feed, Anger, Pommel Strike, Demon Form, Whirlwind, Infernal Blade.
- Relics at the end: Burning Blood, Regal Pillow, Golden Idol, PreservedInsect, Odd Mushroom.

### Run 35

- Seed 4286837648188794982, started 14:20 (record folder `20261114-141930`).
- Ascension 20, run rules 2, controller 2899ba05. Reached floor 16 (act 1); died on floor 16 to Hexaghost (score 212).
- Act 1 boss: Hexaghost, lost, HP 70 -> 0.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 64 (70), F2 63 (69), F4 65 (71), F6 29 (35), F7 39 (45), F8 35 (41), F11 29 (35), F12 34 (40), F13 34 (40), F14 40 (46), F16 0.
- Deck at the end (19): AscendersBane, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash, Shockwave, Iron Wave, Rage, Thunderclap, Seeing Red, Carnage, Reckless Charge, Armaments, Wild Strike.
- Relics at the end: Burning Blood, Strawberry, Letter Opener, Potion Belt.

### Run 36

- Seed -4147427320273187147, started 14:28 (record folder `20261114-142823`).
- Ascension 20, run rules 2, controller 287af073. Reached floor 16 (act 1); died on floor 16 to SlimeBoss (score 216).
- Act 1 boss: Slime Boss, lost, HP 64 -> 0.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 62 (68), F2 61 (67), F3 59 (65), F4 64 (70), F5 41 (47), F7 30 (36), F10 58 (64), F11 24 (30), F12 30 (36), F14 58 (64), F16 0.
- Deck at the end (20): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Shrug It Off+, Twin Strike+, Iron Wave, Ghostly Armor, Cleave, Inflame, Power Through, Intimidate, Flex.
- Relics at the end: Burning Blood, Anchor, Ornamental Fan.

### Run 37

- Seed 7503180595540485795, started 14:41 (record folder `20261114-144115`).
- Ascension 20, run rules 2, controller c1eb9b84. Reached floor 8 (act 1); died on floor 8 to Lagavulin (score 120).
- Act 1 boss: Slime Boss.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 50 (56), F2 55 (61), F4 52 (58), F5 51 (57), F6 6 (12), F7 14 (20), F8 0.
- Deck at the end (17): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash, Sword Boomerang, Twin Strike, Flex, Iron Wave, Reckless Charge, Pummel.
- Relics at the end: Burning Blood, MawBank, Blood Vial.

### Run 38

- Seed 1787889665870883969, started 14:47 (record folder `20261114-144639`).
- Ascension 20, run rules 2, controller 19072822. Reached floor 16 (act 1); died on floor 16 to TheGuardian (score 216).
- Act 1 boss: The Guardian, lost, HP 61 -> 0.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 64 (70), F2 69 (75), F3 73 (79), F4 23 (29), F5 13 (19), F8 33 (39), F10 33 (39), F11 31 (37), F13 30 (36), F14 31 (37), F16 0.
- Deck at the end (20): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash, Pummel, Blood for Blood, Pommel Strike, Wild Strike, Flex, Armaments, Reckless Charge, Armaments, Headbutt.
- Relics at the end: Burning Blood, Bag of Preparation, Nunchaku.

### Run 39

- Seed -319021159679698639, started 14:56 (record folder `20261114-145619`).
- Ascension 20, run rules 2, controller fefbde56. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: Slime Boss, beaten, HP 68 -> 34 (40 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 51 (57), F2 57 (63), F4 57 (63), F5 57 (69), F6 55 (61), F7 61 (54), F8 38 (44), F10 40 (46), F12 48 (54), F13 50 (56), F14 40 (46), F16 34 (40).
- Deck at the end (22): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Clash+, Perfected Strike, Reaper, Fire Breathing, Evolve, Second Wind, Shrug It Off, Twin Strike, Immolate, Pommel Strike, Demon Form.
- Relics at the end: Burning Blood, Dream Catcher, Bottled Lightning, Fusion Hammer.

### Run 40

- Seed -706931013773583234, started 15:10 (record folder `20261114-150850`).
- Ascension 20, run rules 2, controller 6609cf6e. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: The Guardian, beaten, HP 54 -> 8 (14 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 61 (67), F2 52 (58), F3 57 (63), F4 61 (67), F5 46 (52), F7 48 (54), F8 17 (23), F12 42 (48), F13 18 (24), F14 24 (30), F16 8 (14).
- Deck at the end (20): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Sever Soul, Pommel Strike, Anger, Perfected Strike, Anger, Ghostly Armor, Rage, Clash, Bludgeon.
- Relics at the end: Burning Blood, Shovel, Odd Mushroom, Kunai, Ectoplasm.

### Run 41

- Seed -1905421926229433491, started 15:19 (record folder `20261114-151903`).
- Ascension 20, run rules 2, controller 7bc28014. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: Slime Boss, beaten, HP 85 -> 33 (39 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 66 (72), F3 68 (74), F7 73 (75), F10 55 (61), F11 61 (67), F12 46 (52), F14 57 (63), F16 33 (39).
- Deck at the end (15): AscendersBane, Strike, Strike, Strike+, Strike, Defend, Defend, Defend, Defend, Bash+, Twin Strike+, Clash+, Rage+, True Grit, Armaments.
- Relics at the end: Burning Blood, Darkstone Periapt, Whetstone, Runic Pyramid.

### Run 42

- Seed -2880377323971371123, started 15:28 (record folder `20261114-152744`).
- Ascension 20, run rules 2, controller 74e80968. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: The Guardian, beaten, HP 66 -> 37 (42 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 50 (56), F2 55 (61), F3 61 (67), F5 62 (68), F7 68 (74), F10 50 (56), F11 46 (52), F12 50 (56), F13 58 (64), F16 37 (42).
- Deck at the end (19): AscendersBane, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Trip+, Twin Strike, Power Through, Inflame, Pommel Strike, Heavy Blade, Berserk, Metallicize, Pummel, Bludgeon.
- Relics at the end: Burning Blood, Blood Vial, Sundial, Black Star.

### Run 43

- Seed -1522611018025309686, started 15:38 (record folder `20261114-153733`).
- Ascension 20, run rules 2, controller 7828f4e5. Reached floor 16 (act 1); died on floor 16 to TheGuardian (score 228).
- Act 1 boss: The Guardian, lost, HP 50 -> 0.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 72 (78), F2 68 (74), F4 74 (80), F5 72 (78), F7 39 (45), F8 43 (49), F10 39 (45), F11 14 (20), F12 18 (24), F16 0.
- Deck at the end (19): AscendersBane, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Heavy Blade, Shrug It Off, Dropkick, Warcry, Perfected Strike, Clothesline, Thunderclap, Seeing Red, Twin Strike.
- Relics at the end: Burning Blood, Calipers, Letter Opener, Blood Vial.

### Run 44

- Seed -5347611068612097897, started 15:49 (record folder `20261114-154828`).
- Ascension 20, run rules 2, controller 8ace2e9c. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: Slime Boss, beaten, HP 66 -> 3 (9 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 56 (62), F3 55 (61), F4 61 (67), F5 66 (68), F7 12 (18), F8 14 (20), F14 40 (46), F16 3 (9).
- Deck at the end (18): AscendersBane, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Pommel Strike, Carnage, Battle Trance, Shockwave, Fiend Fire, Shockwave, Anger, Reaper.
- Relics at the end: Burning Blood, Golden Idol, Centennial Puzzle, Nunchaku, Snecko Eye.

### Run 45

- Seed 8703057957420699164, started 16:04 (record folder `20261114-160340`).
- Ascension 20, run rules 2, controller dea9c121. Reached floor 16 (act 1); died on floor 16 to Hexaghost (score 216).
- Act 1 boss: Hexaghost, lost, HP 50 -> 0.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 54 (60), F2 58 (64), F3 63 (69), F4 55 (61), F5 52 (58), F7 50 (56), F10 55 (61), F11 61 (67), F12 58 (64), F14 22 (28), F16 0.
- Deck at the end (17): AscendersBane, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Iron Wave, Heavy Blade, True Grit, Iron Wave, Clash, Shockwave, Sever Soul.
- Relics at the end: Burning Blood, Boot, Bag of Preparation, Bronze Scales.

### Run 46

- Seed 255410107091668840, started 16:15 (record folder `20261114-161502`).
- Ascension 20, run rules 2, controller a15f73f2. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: The Guardian, beaten, HP 71 -> 32 (38 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 62 (68), F3 52 (58), F4 43 (49), F5 42 (48), F6 22 (28), F7 9 (15), F11 40 (46), F12 43 (49), F16 32 (38).
- Deck at the end (19): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Clash+, Disarm+, Flex, True Grit, Flame Barrier, Clash, Double Tap, CurseOfTheBell.
- Relics at the end: Burning Blood, Smiling Mask, Blue Candle, Calling Bell, Akabeko, Frozen Egg 2, Torii.

### Run 47

- Seed -9153023356173534844, started 16:24 (record folder `20261114-162327`).
- Ascension 20, run rules 2, controller 2539d381. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: Slime Boss, beaten, HP 68 -> 52 (58 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 71 (77), F2 71 (77), F3 65 (71), F4 47 (53), F6 33 (39), F8 39 (45), F10 40 (46), F11 38 (44), F12 32 (38), F14 62 (68), F16 52 (58).
- Deck at the end (19): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Fire Breathing, Shrug It Off, Fire Breathing, Immolate, Armaments, Pommel Strike, Flame Barrier, Impervious.
- Relics at the end: Burning Blood, WingedGreaves, TungstenRod, Fusion Hammer.

### Run 48

- Seed 6341141307583313079, started 16:33 (record folder `20261114-163247`).
- Ascension 20, run rules 2, controller 2539d381. Reached floor 16 (act 1); died on floor 16 to Hexaghost (score 196).
- Act 1 boss: Hexaghost, lost, HP 67 -> 0.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 67 (73), F2 72 (75), F3 66 (72), F4 58 (64), F7 45 (51), F11 23 (29), F12 25 (31), F13 22 (28), F14 28 (34), F16 0.
- Deck at the end (18): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Wild Strike+, Iron Wave+, Carnage, Havoc, Body Slam, Clash, Flame Barrier.
- Relics at the end: Burning Blood, Eternal Feather.

### Run 49

- Seed -864058454090255540, started 16:43 (record folder `20261114-164227`).
- Ascension 20, run rules 2, controller 2c21bc15. Reached floor 12 (act 1); died on floor 12 to AcidSlime_L (score 144).
- Act 1 boss: Slime Boss.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 62 (68), F2 56 (62), F7 62 (68), F8 61 (67), F10 21 (27), F11 6 (12), F12 0.
- Deck at the end (14): AscendersBane, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Pommel Strike, True Grit, Rupture, Battle Trance, Inflame.
- Relics at the end: Burning Blood, Anchor, Dream Catcher.

### Run 50

- Seed 2402730110775142345, started 16:59 (record folder `20261114-165857`).
- Ascension 20, run rules 2, controller 2c21bc15. Reached floor 8 (act 1); died on floor 8 to Lagavulin (score 120).
- Act 1 boss: The Guardian.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 69 (75), F3 68 (74), F4 65 (71), F5 61 (67), F6 19 (25), F7 9 (15), F8 0.
- Deck at the end (15): AscendersBane, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash, Armaments, Sever Soul, Warcry, Flame Barrier, Headbutt.
- Relics at the end: Burning Blood, Self Forming Clay.

### Run 51

- Seed -7961151478036639737, started 17:08 (record folder `20261114-170731`).
- Ascension 20, run rules 3, controller e28d1215. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: Hexaghost, beaten, HP 76 -> 18 (23 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 74 (80), F3 70 (76), F7 66 (71), F10 65 (71), F11 68 (74), F12 66 (72), F13 70 (75), F14 70 (76), F16 18 (23).
- Deck at the end (16): AscendersBane, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Combust+, Rage+, Armaments, Clash, Fire Breathing, Immolate.
- Relics at the end: Burning Blood, Thread and Needle, Snecko Eye.

### Run 52

- Seed -8789417379975922200, started 17:14 (record folder `20261114-171408`).
- Ascension 20, run rules 3, controller 2471a361. Reached floor 10 (act 1); died on floor 10 to GremlinNob (score 116).
- Act 1 boss: The Guardian.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 69 (75), F3 69 (75), F4 73 (79), F5 22 (28), F10 0.
- Deck at the end (12): AscendersBane, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash, True Grit, Perfected Strike.
- Relics at the end: Burning Blood, Golden Idol, Regal Pillow.

### Run 53

- Seed 2530050266444033605, started 17:20 (record folder `20261114-171927`).
- Ascension 20, run rules 3, controller bcb8ee54. Reached floor 16 (act 1); died on floor 16 to Hexaghost (score 224).
- Act 1 boss: Hexaghost, lost, HP 69 -> 0.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 68 (74), F4 73 (79), F5 75 (81), F6 30 (36), F8 25 (31), F11 47 (53), F13 52 (58), F14 39 (45), F16 0.
- Deck at the end (16): AscendersBane, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash, Wild Strike, Perfected Strike, Headbutt, Anger, Power Through, Thunderclap.
- Relics at the end: Burning Blood, Girya, Self Forming Clay, Happy Flower, HornCleat.

### Run 54

- Seed 926744873887662233, started 17:30 (record folder `20261114-173008`).
- Ascension 20, run rules 4, controller 48f2aafc. Reached floor 16 (act 1); died on floor 16 to Hexaghost (score 258).
- Act 1 boss: Hexaghost, lost, HP 64 -> 0.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 61 (67), F2 44 (50), F3 49 (55), F7 46 (52), F8 48 (54), F11 50 (56), F13 52 (58), F14 58 (64), F16 0.
- Deck at the end (18): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Shrug It Off+, Heavy Blade+, Havoc, Havoc, Perfected Strike, Reaper, Headbutt.
- Relics at the end: Burning Blood, HornCleat, Thread and Needle.

### Run 55

- Seed 3044931127094874255, started 17:38 (record folder `20261114-173806`).
- Ascension 20, run rules 4, controller 48f2aafc. Reached floor 6 (act 1); died on floor 6 to Sentry + Sentry + Sentry (score 76).
- Act 1 boss: Hexaghost.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 62 (68), F3 75, F4 69 (75), F5 67 (73), F6 0.
- Deck at the end (15): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash, Carnage, Armaments, Intimidate, Warcry.
- Relics at the end: Burning Blood, MealTicket.

### Run 56

- Seed -3228720725002353091, started 17:42 (record folder `20261114-174227`).
- Ascension 20, run rules 4, controller f4e88da6. Reached floor 16 (act 1); died on floor 16 to SlimeBoss (score 244).
- Act 1 boss: Slime Boss, lost, HP 38 -> 0.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 74 (80), F2 76 (82), F3 80 (82), F4 78 (82), F6 51 (57), F8 47 (53), F11 36 (42), F13 69 (75), F14 5 (11), F16 0.
- Deck at the end (18): AscendersBane, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Flex, Twin Strike, Armaments, Clash, Clash, Body Slam, Rampage, Perfected Strike.
- Relics at the end: Burning Blood, Pear, InkBottle, Ancient Tea Set, Lantern.

### Run 57

- Seed 7827083943775505261, started 17:58 (record folder `20261114-175707`).
- Ascension 20, run rules 5, controller 3fd17834. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: Slime Boss, beaten, HP 90 -> 59 (65 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 70 (76), F2 63 (69), F4 79 (85), F5 81 (87), F6 58 (64), F7 52 (58), F10 56 (62), F12 57 (63), F13 57 (63), F16 59 (65).
- Deck at the end (19): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash, Uppercut, Clash, Anger, Anger, Demon Form, Heavy Blade, Thunderclap, Corruption.
- Relics at the end: Burning Blood, Pear, Pen Nib, Shuriken, Coffee Dripper.

### Run 58

- Seed 3240554893271370845, started 18:08 (record folder `20261114-180752`).
- Ascension 20, run rules 5, fight guard 1, controller 6acc764a. Reached floor 16 (act 1); died on floor 16 to Hexaghost (score 188).
- Act 1 boss: Hexaghost, lost, HP 77 -> 0.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 60 (66), F3 66 (72), F5 70 (75), F10 73 (75), F11 64 (70), F13 75 (80), F14 71 (77), F16 0.
- Deck at the end (16): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Pommel Strike+, Sever Soul, Seeing Red, Hemokinesis, Iron Wave.
- Relics at the end: Burning Blood, Unceasing Top.

### Run 59

- Seed -6027430396510908462, started 18:11 (record folder `20261114-180752`).
- Ascension 20, run rules 5, fight guard 1, controller 6acc764a. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: Slime Boss, beaten, HP 60 -> 49 (55 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 61 (67), F2 66 (72), F3 68 (74), F8 64 (70), F11 70 (75), F13 59 (65), F14 54 (60), F16 49 (55).
- Deck at the end (16): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Metallicize+, Armaments+, Fire Breathing, Armaments, Reaper.
- Relics at the end: Burning Blood, Bag of Marbles, Runic Pyramid.

### Run 60

- Seed -6283101093061905430, started 18:16 (record folder `20261114-181602`).
- Ascension 20, run rules 5, fight guard 1, controller 88b189c1. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: Slime Boss, beaten, HP 75 -> 41 (38 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 62 (68), F3 67 (73), F4 54 (60), F5 58 (64), F6 38 (44), F8 40 (46), F10 48 (54), F11 44 (50), F12 44 (50), F13 47 (53), F14 50 (56), F16 41 (38).
- Deck at the end (19): AscendersBane, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash, Clash, Whirlwind, Fire Breathing, Shrug It Off, Thunderclap, Metallicize, Clothesline, Pommel Strike, Reaper.
- Relics at the end: Burning Blood, CeramicFish, Blood Vial, Fusion Hammer.

### Run 61

- Seed 4071802193247872244, started 18:23 (record folder `20261114-182252`).
- Ascension 20, run rules 5, fight guard 1, controller 08f062ff. Reached floor 16 (act 1); died on floor 16 to Hexaghost (score 192).
- Act 1 boss: Hexaghost, lost, HP 66 -> 0.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 56 (62), F2 50 (56), F3 49 (55), F4 36 (42), F7 61 (67), F11 59 (65), F13 59 (65), F14 60 (66), F16 0.
- Deck at the end (15): AscendersBane, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Carnage+, Shrug It Off, Spot Weakness, Sever Soul, Sword Boomerang.
- Relics at the end: Burning Blood, Letter Opener.

### Run 62

- Seed -4952159854125664056, started 18:27 (record folder `20261114-182252`).
- Ascension 20, run rules 5, fight guard 1, controller 08f062ff. Reached floor 16 (act 1); died on floor 16 to Hexaghost (score 208).
- Act 1 boss: Hexaghost, lost, HP 77 -> 0.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 58 (64), F2 59 (65), F3 65 (71), F4 51 (57), F6 29 (35), F12 69 (75), F13 71 (77), F14 71 (77), F16 0.
- Deck at the end (19): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Iron Wave+, True Grit+, Armaments, Wild Strike, Seeing Red, Anger, Juggernaut, Rampage.
- Relics at the end: Burning Blood, Pear, Champion Belt.

### Run 63

- Seed 2599543023241001866, started 18:32 (record folder `20261114-182252`).
- Ascension 20, run rules 5, fight guard 1, controller 08f062ff. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: Slime Boss, beaten, HP 68 -> 39.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 65 (71), F2 62 (68), F3 74 (80), F4 66 (72), F5 69 (75), F6 15 (21), F8 38 (44), F10 37 (43), F13 67 (73), F14 62 (68), F16 39.
- Deck at the end (20): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Iron Wave, Pommel Strike, Iron Wave, Heavy Blade, Flex, Spot Weakness, Shrug It Off, Fire Breathing, CurseOfTheBell.
- Relics at the end: Burning Blood, MawBank, Bag of Marbles, Calling Bell, Smiling Mask, Paper Frog, Incense Burner.

### Run 64

- Seed -5142770969961821495, started 18:41 (record folder `20261114-184054`).
- Ascension 20, run rules 5, fight guard 1, controller 443431a6. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: Slime Boss, beaten, HP 66 -> 40 (46 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 49 (55), F3 55 (61), F4 44 (50), F5 50 (56), F7 24 (30), F8 30 (36), F11 55 (61), F12 60 (66), F16 40 (46).
- Deck at the end (16): AscendersBane, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Carnage+, Evolve, Whirlwind, Thunderclap, Armaments, Spot Weakness, Clash.
- Relics at the end: Burning Blood, MealTicket, Potion Belt, Runic Cube.

### Run 65

- Seed 3097370085526979066, started 18:49 (record folder `20261114-184841`).
- Ascension 20, run rules 5, fight guard 1, controller add18f0c. Reached floor 16 (act 1); died on floor 16 to SlimeBoss (score 212).
- Act 1 boss: Slime Boss, lost, HP 77 -> 0.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 68 (74), F4 71 (77), F6 66 (72), F7 72 (78), F8 68 (74), F10 64 (70), F12 70 (76), F13 76 (82), F14 71 (77), F16 0.
- Deck at the end (18): AscendersBane, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Heavy Blade+, Anger+, Shrug It Off, Warcry, Thunderclap, Twin Strike, Heavy Blade, Disarm.
- Relics at the end: Burning Blood, Whetstone.

### Run 66

- Seed 2482528129127376130, started 18:54 (record folder `20261114-184841`).
- Ascension 20, run rules 5, fight guard 1, controller add18f0c. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: The Guardian, beaten, HP 58 -> 34 (36 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 63 (69), F2 63 (69), F3 69 (75), F4 65 (71), F5 49 (55), F8 27 (33), F11 45 (51), F12 40 (46), F13 27 (33), F14 30 (36), F16 34 (36).
- Deck at the end (19): AscendersBane, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Clash, Uppercut, Pommel Strike, Perfected Strike, Flex, Armaments, Searing Blow, Disarm, Fiend Fire.
- Relics at the end: Burning Blood, Bottled Flame, Tiny Chest, Runic Cube.

### Run 67

- Seed -8852864157786367094, started 19:01 (record folder `20261114-190125`).
- Ascension 20, run rules 5, fight guard 1, controller 42ee09e5. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: The Guardian, beaten, HP 62 -> 30 (32 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 49 (55), F3 54 (60), F4 60 (66), F5 65 (71), F8 53 (59), F10 58 (64), F11 59 (65), F12 64 (70), F14 56 (62), F16 30 (32).
- Deck at the end (20): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Pummel+, Spot Weakness+, Armaments, Disarm, Disarm, Shrug It Off, Cleave, Disarm, Impervious.
- Relics at the end: Burning Blood, Bag of Preparation, Happy Flower, Ectoplasm.

### Run 68

- Seed 3965527673310578912, started 19:09 (record folder `20261114-190853`).
- Ascension 20, run rules 5, fight guard 1, controller a57e18a0. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: The Guardian, beaten, HP 71 -> 22 (25 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 67 (73), F2 70 (75), F3 68 (74), F4 63 (69), F5 69 (75), F7 50 (56), F13 47 (53), F14 43 (49), F16 22 (25).
- Deck at the end (18): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Perfected Strike+, Wild Strike+, Dropkick+, Thunderclap, Spot Weakness, Flame Barrier, Impervious.
- Relics at the end: Burning Blood, PreservedInsect, Shuriken, Sozu.

### Run 69

- Seed 8837619465522875918, started 19:17 (record folder `20261114-191707`).
- Ascension 20, run rules 5, fight guard 1, controller d89be186. Reached floor 16 (act 1); died on floor 16 to TheGuardian (score 212).
- Act 1 boss: The Guardian, lost, HP 44 -> 0.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 61 (67), F2 66 (72), F3 66 (72), F4 72 (75), F7 65 (71), F8 32 (38), F10 32 (38), F11 26 (32), F14 16 (22), F16 0.
- Deck at the end (16): AscendersBane, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Dropkick, Reckless Charge, Armaments+, Clothesline, Spot Weakness+, Havoc.
- Relics at the end: Burning Blood, PreservedInsect, War Paint.

### Run 70

- Seed 5563724835141953500, started 19:26 (record folder `20261114-191707`).
- Ascension 20, run rules 5, fight guard 1, controller d89be186. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: Slime Boss, beaten, HP 84 -> 44 (50 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 61 (67), F2 66 (72), F3 68 (74), F5 68 (74), F7 70 (75), F8 60 (66), F10 68 (74), F12 73 (79), F16 44 (50).
- Deck at the end (17): AscendersBane, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Iron Wave+, Anger+, Armaments+, Feel No Pain, Feel No Pain, Reckless Charge, Juggernaut, Juggernaut.
- Relics at the end: Burning Blood, Pear, Cursed Key.

### Run 71

- Seed 5479015772466851150, started 19:40 (record folder `20261114-194000`).
- Ascension 20, run rules 5, fight guard 1, controller c9e26e84. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: Slime Boss, beaten, HP 60 -> 33 (39 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 67 (73), F2 66 (72), F3 65 (71), F4 58 (64), F5 64 (70), F7 62 (68), F8 60 (66), F10 49 (55), F12 48 (54), F13 32 (38), F16 33 (39).
- Deck at the end (20): AscendersBane, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Perfected Strike+, Anger, Shockwave, Ghostly Armor, Impervious, Spot Weakness, Cleave, Anger, Rampage, Offering.
- Relics at the end: Burning Blood, Sundial, Odd Mushroom, Ornamental Fan, Ectoplasm.

### Run 72

- Seed -15871794944967335, started 19:47 (record folder `20261114-194733`).
- Ascension 20, run rules 5, fight guard 1, controller 51e6e853. Reached floor 10 (act 1); died on floor 10 to GremlinNob (score 144).
- Act 1 boss: Slime Boss.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 67 (73), F2 61 (67), F3 57 (63), F4 46 (52), F5 39 (45), F7 30 (21), F8 12 (18), F10 0.
- Deck at the end (17): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Fire Breathing+, True Grit, Clothesline, Armaments, Iron Wave, Wild Strike.
- Relics at the end: Burning Blood, CeramicFish, Bag of Preparation.

### Run 73

- Seed 6106718228375544733, started 19:52 (record folder `20261114-194733`).
- Ascension 20, run rules 5, fight guard 1, controller 51e6e853. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: Hexaghost, beaten, HP 67 -> 24 (30 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 69 (75), F2 68 (74), F3 74 (80), F4 78 (82), F5 51 (57), F7 35 (41), F10 55 (61), F11 50 (56), F12 40 (46), F13 37 (43), F16 24 (30).
- Deck at the end (17): AscendersBane, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Iron Wave, Iron Wave, Anger, Sword Boomerang, Evolve, Rage, Body Slam, Impervious.
- Relics at the end: Burning Blood, Art of War, PreservedInsect, Empty Cage.

### Run 74

- Seed -725174324252226590, started 20:01 (record folder `20261114-200104`).
- Ascension 20, run rules 5, fight guard 1, controller 29584a35. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: Slime Boss, beaten, HP 58 -> 24 (30 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 69 (75), F3 66 (72), F4 72 (78), F5 64 (70), F6 30 (36), F8 35 (41), F11 64 (70), F12 69 (75), F14 28 (34), F16 24 (30).
- Deck at the end (16): AscendersBane, Strike, Strike, Defend, Defend, Defend, Defend, Bash, Iron Wave, Anger, Battle Trance, Iron Wave, Armaments, Perfected Strike, Juggernaut, Barricade.
- Relics at the end: Burning Blood, Torii, Bottled Flame, Mummified Hand, Astrolabe.

### Run 75

- Seed -742714235150748835, started 20:14 (record folder `20261114-201358`).
- Ascension 20, run rules 5, fight guard 1, controller af1862cb. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: The Guardian, beaten, HP 82 -> 69 (71 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 66 (72), F2 60 (66), F3 66 (72), F4 63 (69), F7 61 (67), F10 40 (46), F11 43 (49), F13 73 (79), F14 76 (82), F16 69 (71).
- Deck at the end (20): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Clothesline+, Clash+, Inflame, Flex, Disarm, Pommel Strike, Spot Weakness, Sword Boomerang, True Grit.
- Relics at the end: Burning Blood, InkBottle, Fusion Hammer.

### Run 76

- Seed 6950095771528906389, started 20:19 (record folder `20261114-201903`).
- Ascension 20, run rules 5, fight guard 1, controller 6b5bacd0. Reached floor 8 (act 1); died on floor 8 to Lagavulin (score 112).
- Act 1 boss: Hexaghost.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 67 (73), F2 64 (70), F4 68 (74), F5 71 (77), F6 26 (32), F8 0.
- Deck at the end (16): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash, Clothesline, True Grit, Feel No Pain, Second Wind, Fire Breathing.
- Relics at the end: Burning Blood, TungstenRod.

### Run 77

- Seed -7842609651044369469, started 20:22 (record folder `20261114-201903`).
- Ascension 20, run rules 5, fight guard 1, controller 6b5bacd0. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: The Guardian, beaten, HP 81 -> 23 (41 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 55 (61), F2 55 (61), F3 49 (55), F4 47 (53), F5 35 (41), F7 56 (62), F8 52 (58), F11 38 (56), F12 40 (58), F13 52 (58), F14 39 (57), F16 23 (41).
- Deck at the end (22): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash, Blood for Blood, Spot Weakness, Ghostly Armor, Pommel Strike, Twin Strike, Burning Pact, Shrug It Off, Warcry, Flex, Clothesline, Feed.
- Relics at the end: Burning Blood, Meat on the Bone, Velvet Choker.

### Run 78

- Seed 8465514936653568839, started 20:34 (record folder `20261114-203425`).
- Ascension 20, run rules 5, fight guard 1, controller 5b39e471. Reached floor 13 (act 1); died on floor 13 to Looter (score 178).
- Act 1 boss: The Guardian.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 72 (78), F2 64 (70), F3 66 (72), F5 38 (44), F7 30 (36), F10 49 (55), F11 17 (23), F12 5 (11), F13 0.
- Deck at the end (19): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash, Metallicize, Perfected Strike, Clothesline, Thunderclap, Juggernaut, Perfected Strike, Cleave, Ghostly Armor.
- Relics at the end: Burning Blood, Dead Branch, Darkstone Periapt.

### Run 79

- Seed 8661819101062365622, started 20:39 (record folder `20261114-203425`).
- Ascension 20, run rules 5, fight guard 1, controller 5b39e471. Reached floor 10 (act 1); died on floor 10 to Lagavulin (score 140).
- Act 1 boss: Hexaghost.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 61 (67), F2 57 (63), F3 57 (63), F5 63 (69), F7 58 (64), F8 56 (62), F10 0.
- Deck at the end (16): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Wild Strike, Power Through, Heavy Blade, Twin Strike, Armaments.
- Relics at the end: Burning Blood, TungstenRod, MealTicket.

### Run 80

- Seed 4657972869185354020, started 20:43 (record folder `20261114-203425`).
- Ascension 20, run rules 5, fight guard 1, controller 5b39e471. Reached floor 16 (act 1); died on floor 16 to Hexaghost (score 212).
- Act 1 boss: Hexaghost, lost, HP 77 -> 0.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 68 (74), F2 62 (68), F3 51 (57), F4 35 (41), F7 35 (41), F8 41 (47), F11 32 (38), F13 65 (71), F14 71 (77), F16 0.
- Deck at the end (16): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, True Grit, Disarm, Reckless Charge, Shrug It Off, Rage.
- Relics at the end: Burning Blood, Orichalcum, Boot, Frozen Egg 2, Toy Ornithopter.

### Run 81

- Seed 3312247104367054757, started 20:48 (record folder `20261114-203425`).
- Ascension 20, run rules 5, fight guard 1, controller 5b39e471. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: The Guardian, beaten, HP 73 -> 31 (35 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 62 (68), F2 62 (68), F3 67 (73), F5 37 (43), F7 54 (60), F8 36 (42), F10 43 (49), F12 44 (50), F16 31 (35).
- Deck at the end (19): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Flame Barrier, Iron Wave, Blood for Blood, Armaments, Intimidate, Feed, Metallicize, Bludgeon.
- Relics at the end: Burning Blood, Mercury Hourglass, MealTicket, Coffee Dripper.

### Run 82

- Seed -8380325679204191148, started 20:56 (record folder `20261114-205554`).
- Ascension 20, run rules 5, fight guard 1, controller 333daa5d. Reached floor 16 (act 1); died on floor 16 to Hexaghost (score 192).
- Act 1 boss: Hexaghost, lost, HP 68 -> 0.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 58 (64), F2 64 (70), F3 61 (67), F4 53 (59), F6 37 (43), F7 34 (40), F8 29 (35), F14 62 (68), F16 0.
- Deck at the end (16): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Headbutt+, Clash, Perfected Strike, Metallicize, Havoc.
- Relics at the end: Burning Blood, Oddly Smooth Stone.

### Run 83

- Seed -5085640134281314222, started 21:01 (record folder `20261114-205554`).
- Ascension 20, run rules 5, fight guard 1, controller 333daa5d. Reached floor 7 (act 1); died on floor 7 to Lagavulin (score 86).
- Act 1 boss: The Guardian.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 62 (68), F2 54 (60), F3 54 (60), F5 8 (14), F7 0.
- Deck at the end (14): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash, Flame Barrier, Havoc, Infernal Blade.
- Relics at the end: Burning Blood.

### Run 84

- Seed -5492360757243889621, started 21:12 (record folder `20261114-205554`).
- Ascension 20, run rules 5, fight guard 1, controller 333daa5d. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: Slime Boss, beaten, HP 82 -> 58 (64 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 66 (72), F2 71 (77), F3 75 (81), F7 72 (78), F10 59 (65), F12 62 (68), F13 53 (59), F14 53 (59), F16 58 (64).
- Deck at the end (18): AscendersBane, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Battle Trance+, Wild Strike, Intimidate, Pommel Strike, Carnage, Anger, Perfected Strike, Demon Form.
- Relics at the end: Black Blood, Centennial Puzzle, Orichalcum.

### Run 85

- Seed -7105349832389949558, started 21:22 (record folder `20261114-212229`).
- Ascension 20, run rules 5, fight guard 1, controller 1334685f. Reached floor 16 (act 1); died on floor 16 to Hexaghost (score 192).
- Act 1 boss: Hexaghost, lost, HP 48 -> 0.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 70 (76), F2 69 (75), F4 75 (81), F5 81 (82), F7 62 (68), F11 60 (66), F12 50 (56), F13 32 (38), F14 18 (24), F16 0.
- Deck at the end (19): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Perfected Strike+, Iron Wave, Twin Strike, Ghostly Armor, Sever Soul, Clothesline, Shrug It Off, Warcry.
- Relics at the end: Burning Blood, Bottled Lightning, Odd Mushroom.

### Run 86

- Seed -5842089037397876693, started 21:29 (record folder `20261114-212926`).
- Ascension 20, run rules 5, fight guard 1, controller bd0a95cf. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: Slime Boss, beaten, HP 66 -> 31 (37 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 65 (71), F2 70 (75), F3 75, F4 65 (71), F5 54 (60), F7 60 (66), F10 45 (51), F12 45 (51), F13 38 (44), F14 38 (44), F16 31 (37).
- Deck at the end (17): AscendersBane, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Carnage, Shrug It Off, Combust, Heavy Blade, Cleave, Iron Wave, Carnage, Combust, Bloodletting.
- Relics at the end: Burning Blood, Bag of Preparation, Darkstone Periapt, Astrolabe.

### Run 87

- Seed -8917592636621336127, started 21:36 (record folder `20261114-213601`).
- Ascension 20, run rules 5, fight guard 1, controller 867e1d2b. Reached floor 16 (act 1); died on floor 16 to Hexaghost (score 200).
- Act 1 boss: Hexaghost, lost, HP 70 -> 0.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 62 (68), F2 73 (75), F3 75, F5 65 (71), F7 60 (66), F8 66 (70), F10 69 (75), F12 56 (62), F13 65 (71), F14 64 (70), F16 0.
- Deck at the end (20): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Swift Strike+, Whirlwind, Hemokinesis, Cleave, Shockwave, Wild Strike, Power Through, Immolate, Heavy Blade.
- Relics at the end: Burning Blood, Toy Ornithopter.

### Run 88

- Seed -6502403952618655727, started 21:40 (record folder `20261114-213601`).
- Ascension 20, run rules 5, fight guard 1, controller 867e1d2b. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: The Guardian, beaten, HP 78 -> 55 (61 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 71 (77), F2 71 (77), F3 74 (80), F4 75 (81), F6 49 (55), F8 45 (51), F11 35 (41), F13 48 (54), F16 55 (61).
- Deck at the end (20): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Shrug It Off, Disarm, Rampage, True Grit, Fiend Fire, Intimidate, Spot Weakness, Clash, Reaper.
- Relics at the end: Burning Blood, Bag of Marbles, Omamori, Coffee Dripper.

### Run 89

- Seed -1061415185605709155, started 21:47 (record folder `20261114-214717`).
- Ascension 20, run rules 5, fight guard 1, controller 186abde7. Reached floor 17 (act 2); beat the Act 1 boss; stopped when Act 2 started (Act 2 isn't modelled, so it isn't played).
- Act 1 boss: Slime Boss, beaten, HP 76 -> 44 (50 after).
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 69 (75), F2 64 (70), F3 63 (69), F4 65 (71), F5 71 (77), F7 64 (70), F10 65 (71), F11 71 (77), F13 73 (79), F14 68 (74), F16 44 (50).
- Deck at the end (21): AscendersBane, Strike, Strike, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Clothesline+, Wild Strike+, Seeing Red, Uppercut, Armaments, Blood for Blood, Evolve, Anger, Juggernaut, Brutality.
- Relics at the end: Burning Blood, Blood Vial, Mark of Pain.

### Run 90

- Seed 7439922232821094944, started 21:59 (record folder `20261114-215903`).
- Ascension 20, run rules 5, fight guard 1, controller c3792357. Reached floor 16 (act 1); died on floor 16 to Hexaghost (score 204).
- Act 1 boss: Hexaghost, lost, HP 43 -> 0.
- HP at the end of each Act 1 fight (after it, where end-of-fight relics healed): F1 63 (69), F2 61 (67), F3 57 (63), F4 51 (57), F7 44 (50), F8 14 (20), F14 13 (19), F16 0.
- Deck at the end (16): AscendersBane, Strike, Strike, Strike, Defend, Defend, Defend, Defend, Bash+, Thunderclap, Fire Breathing, Cleave, Heavy Blade, Pommel Strike, Anger, Power Through.
- Relics at the end: Burning Blood, Matryoshka, Peace Pipe.

## Fights

| Run | Setting | Floor | Kind | Monsters | HP | Result | Steps matched | Decisions | Think (median / worst) | Fallback |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | A0 r1 | 1 | hallway | AcidSlime_S + SpikeSlime_M | 80 -> 77 (80 after) | won | 7 / 7 | 3 | 0.2 s / 0.5 s |  |
| 1 | A0 r1 | 2 | hallway | FuzzyLouseNormal + FuzzyLouseNormal | 80 -> 74 (80 after) | won | 4 / 4 | 2 | 1.1 s / 2.1 s |  |
| 1 | A0 r1 | 3 | hallway | Cultist | 80 -> 74 (80 after) | won | 7 / 7 | 3 | 0.1 s / 0.1 s |  |
| 1 | A0 r1 | 4 | hallway | FungiBeast + FuzzyLouseDefensive | 80 -> 76 (80 after) | won | 8 / 8 | 3 | 0.5 s / 1.6 s |  |
| 1 | A0 r1 | 7 | hallway | SlaverBlue | 80 -> 73 (79 after) | won | 4 / 4 | 3 | 0.6 s / 0.7 s |  |
| 1 | A0 r1 | 10 | hallway | Looter | 79 -> 74 (80 after) | won | 4 / 4 | 1 | 4.9 s / 4.9 s | card Rampage{damage=13/combat} not in the game's hand |
| 1 | A0 r1 | 11 | hallway | FungiBeast + FungiBeast | 80 -> 75 (80 after) | won | 5 / 5 | 6 | 20.5 s / 34.8 s |  |
| 1 | A0 r1 | 12 | hallway | AcidSlime_S + SpikeSlime_S + SpikeSlime_S + SpikeSlime_S + AcidSlime_S | 80 -> 80 | won | 7 / 7 | 6 | 4.8 s / 17.9 s |  |
| 1 | A0 r1 | 13 | hallway | SlaverRed | 80 -> 72 (78 after) | won | 4 / 4 | 3 | 0.8 s / 1.5 s |  |
| 1 | A0 r1 | 14 | hallway | SpikeSlime_M + Cultist | 78 -> 65 (71 after) | won | 10 / 11 | 14 | 3.3 s / 24.9 s |  |
| 1 | A0 r1 | 16 | boss | TheGuardian | 71 -> 44 (50 after) | won | 29 / 31 | 26 | 6.4 s / 41.6 s |  |
| 1 | A0 r1 | 18 | hallway | Chosen | 80 -> 63 (69 after) | won | - | 0 | - | monster Chosen not loaded |
| 1 | A0 r1 | 20 | hallway | Byrd + Byrd + Byrd | 69 -> 25 (31 after) | won | - | 0 | - | monster Byrd not loaded |
| 2 | A0 r1 | 1 | hallway | AcidSlime_S + SpikeSlime_M | 88 -> 85 (88 after) | won | 6 / 6 | 3 | 0.0 s / 0.1 s |  |
| 2 | A0 r1 | 2 | hallway | Cultist | 88 -> 82 (88 after) | won | 7 / 7 | 3 | 0.0 s / 0.1 s |  |
| 2 | A0 r1 | 3 | hallway | JawWorm | 88 -> 80 (86 after) | won | 6 / 6 | 4 | 0.0 s / 0.1 s |  |
| 2 | A0 r1 | 4 | hallway | FungiBeast + FungiBeast | 86 -> 86 (88 after) | won | 8 / 8 | 4 | 0.6 s / 3.2 s |  |
| 2 | A0 r1 | 6 | elite | Sentry + Sentry + Sentry | 88 -> 49 (55 after) | won | 16 / 16 | 10 | 0.1 s / 1.7 s |  |
| 2 | A0 r1 | 7 | hallway | Looter | 55 -> 50 (56 after) | won | 14 / 14 | 5 | 0.1 s / 0.2 s |  |
| 2 | A0 r1 | 8 | elite | Lagavulin | 56 -> 46 (52 after) | won | 22 / 22 | 11 | 0.1 s / 0.9 s |  |
| 2 | A0 r1 | 11 | hallway | FuzzyLouseNormal + FuzzyLouseNormal + FuzzyLouseNormal | 78 -> 76 (82 after) | won | 12 / 12 | 9 | 11.8 s / 110.7 s |  |
| 2 | A0 r1 | 12 | hallway | FungiBeast + AcidSlime_M | 82 -> 79 (85 after) | won | 20 / 22 | 10 | 0.6 s / 15.4 s |  |
| 2 | A0 r1 | 13 | hallway | SlaverBlue | 85 -> 84 (88 after) | won | 12 / 12 | 5 | 1.6 s / 3.3 s | the plan has no pick here |
| 2 | A0 r1 | 14 | hallway | AcidSlime_L | 88 -> 77 (83 after) | won | 16 / 16 | 8 | 1.3 s / 17.5 s |  |
| 2 | A0 r1 | 16 | boss | TheGuardian | 83 -> 61 (67 after) | won | 25 / 26 | 11 | 0.5 s / 13.1 s |  |
| 2 | A0 r1 | 18 | hallway | Shelled Parasite | 88 -> 64 (70 after) | won | - | 0 | - | monster Shelled Parasite not loaded |
| 2 | A0 r1 | 20 | hallway | SphericGuardian | 70 -> 39 (45 after) | won | - | 0 | - | monster SphericGuardian not loaded |
| 2 | A0 r1 | 21 | hallway | Byrd + Chosen | 45 -> 9 (15 after) | won | - | 0 | - | monster Byrd not loaded |
| 2 | A0 r1 | 22 | hallway | Snecko | 15 -> 15 (21 after) | won | - | 0 | - | monster Snecko not loaded |
| 2 | A0 r1 | 25 | hallway | Cultist + Chosen | 47 -> 4 (10 after) | won | - | 0 | - | move None of Cultist not mapped |
| 2 | A0 r1 | 27 | hallway | Centurion + Healer | 20 -> 0 | **lost** | - | 0 | - | monster Centurion not loaded |
| 3 | A0 r1 | 1 | hallway | JawWorm | 80 -> 71 (77 after) | won | 12 / 12 | 5 | 0.0 s / 0.1 s |  |
| 3 | A0 r1 | 2 | hallway | AcidSlime_S + SpikeSlime_M | 77 -> 77 (80 after) | won | 9 / 9 | 4 | 0.1 s / 0.2 s |  |
| 4 | A0 r1 | 1 | hallway | FuzzyLouseDefensive + FuzzyLouseDefensive | 80 -> 73 (79 after) | won | 5 / 5 | 2 | 2.3 s / 2.3 s |  |
| 4 | A0 r1 | 2 | hallway | JawWorm | 79 -> 68 (74 after) | won | 7 / 7 | 3 | 0.3 s / 9.8 s |  |
| 4 | A0 r1 | 3 | hallway | AcidSlime_S + SpikeSlime_M | 74 -> 74 (80 after) | won | 9 / 9 | 3 | 2.3 s / 4.5 s |  |
| 4 | A0 r1 | 5 | hallway | GremlinWarrior + GremlinTsundere + GremlinWizard + GremlinFat | 74 -> 53 (59 after) | won | 21 / 21 | 12 | 2.1 s / 55.5 s |  |
| 4 | A0 r1 | 7 | elite | Sentry + Sentry + Sentry | 59 -> 36 (42 after) | won | 23 / 23 | 11 | 11.5 s / 33.0 s |  |
| 4 | A0 r1 | 8 | hallway | Looter | 42 -> 37 (43 after) | won | 6 / 6 | 3 | 5.6 s / 5.9 s |  |
| 4 | A0 r1 | 10 | elite | Lagavulin | 43 -> 33 (39 after) | won | 3 / 3 | 5 | 20.6 s / 24.8 s | card Strike{cost=0/combat} not in the game's hand |
| 4 | A0 r1 | 11 | hallway | SpikeSlime_S + SpikeSlime_S + SpikeSlime_S + AcidSlime_S + AcidSlime_S | 39 -> 39 (45 after) | won | 7 / 7 | 8 | 5.2 s / 7.1 s |  |
| 4 | A0 r1 | 12 | elite | Sentry + Sentry + Sentry | 45 -> 37 (43 after) | won | 17 / 17 | 15 | 11.7 s / 23.9 s |  |
| 4 | A0 r1 | 13 | hallway | AcidSlime_M + SlaverBlue | 43 -> 31 (37 after) | won | 9 / 9 | 7 | 8.1 s / 14.7 s |  |
| 4 | A0 r1 | 14 | hallway | SlaverBlue | 37 -> 30 (36 after) | won | 6 / 6 | 3 | 1.6 s / 4.3 s |  |
| 4 | A0 r1 | 16 | boss | SlimeBoss | 70 -> 69 (74 after) | won | 26 / 26 | 28 | 8.7 s / 14.3 s |  |
| 4 | A0 r1 | 18 | hallway | Chosen | 74 -> 37 (43 after) | won | - | 0 | - | monster Chosen not loaded |
| 4 | A0 r1 | 19 | hallway | SphericGuardian | 43 -> 38 (44 after) | won | - | 0 | - | monster SphericGuardian not loaded |
| 4 | A0 r1 | 20 | hallway | SnakePlant | 44 -> 13 (19 after) | won | - | 0 | - | monster SnakePlant not loaded |
| 4 | A0 r1 | 23 | hallway | Sentry + SphericGuardian | 19 -> 0 | **lost** | - | 0 | - | monster SphericGuardian not loaded |
| 5 | A0 r1 | 1 | hallway | Cultist | 80 -> 74 (80 after) | won | 8 / 8 | 3 | 0.0 s / 0.3 s |  |
| 5 | A0 r1 | 3 | hallway | JawWorm | 80 -> 74 (80 after) | won | 7 / 7 | 3 | 0.1 s / 0.1 s |  |
| 6 | A0 r1 | 1 | hallway | AcidSlime_S + SpikeSlime_M | 80 -> 77 (80 after) | won | 8 / 8 | 4 | 0.0 s / 0.2 s |  |
| 6 | A0 r1 | 2 | hallway | Cultist | 80 -> 74 (80 after) | won | 7 / 7 | 3 | 0.0 s / 0.0 s |  |
| 6 | A0 r1 | 3 | hallway | JawWorm | 80 -> 77 (80 after) | won | 8 / 8 | 5 | 0.9 s / 1.5 s |  |
| 6 | A0 r1 | 4 | hallway | FungiBeast + SpikeSlime_M | 80 -> 76 (80 after) | won | 6 / 6 | 3 | 0.1 s / 2.1 s |  |
| 6 | A0 r1 | 5 | hallway | GremlinWarrior + GremlinThief + GremlinThief + GremlinTsundere | 80 -> 76 (80 after) | won | 10 / 10 | 5 | 0.2 s / 3.4 s |  |
| 6 | A0 r1 | 10 | hallway | FuzzyLouseNormal + FuzzyLouseDefensive + FuzzyLouseDefensive | 80 -> 75 (80 after) | won | 11 / 11 | 5 | 0.1 s / 5.3 s |  |
| 6 | A0 r1 | 11 | hallway | SlaverBlue | 80 -> 76 (80 after) | won | 10 / 10 | 5 | 0.1 s / 0.3 s |  |
| 6 | A0 r1 | 12 | hallway | FungiBeast + FuzzyLouseDefensive | 80 -> 76 (80 after) | won | 6 / 6 | 2 | 0.9 s / 1.7 s |  |
| 6 | A0 r1 | 13 | hallway | FuzzyLouseDefensive + FuzzyLouseDefensive + FuzzyLouseNormal | 80 -> 72 (78 after) | won | 6 / 6 | 3 | 0.2 s / 8.1 s |  |
| 6 | A0 r1 | 14 | hallway | AcidSlime_S + SpikeSlime_S + SpikeSlime_S + SpikeSlime_S + AcidSlime_S | 78 -> 68 (74 after) | won | 10 / 10 | 4 | 0.1 s / 10.4 s |  |
| 6 | A0 r1 | 16 | boss | TheGuardian | 80 -> 43 (49 after) | won | 24 / 24 | 11 | 0.1 s / 0.3 s |  |
| 6 | A0 r1 | 18 | hallway | Looter + Mugger | 80 -> 47 (53 after) | won | - | 0 | - | move None of Looter not mapped |
| 6 | A0 r1 | 20 | hallway | Shelled Parasite | 53 -> 27 (31 after) | won | - | 0 | - | monster Shelled Parasite not loaded |
| 6 | A0 r1 | 21 | hallway | Cultist + Cultist + Cultist | 31 -> 0 | **lost** | - | 0 | - | move None of Cultist not mapped |
| 7 | A0 r1 | 1 | hallway | AcidSlime_S + SpikeSlime_M | 80 -> 76 (80 after) | won | 8 / 8 | 4 | 0.1 s / 0.1 s |  |
| 7 | A0 r1 | 2 | hallway | JawWorm | 80 -> 76 (80 after) | won | 9 / 9 | 5 | 0.1 s / 3.2 s |  |
| 7 | A0 r1 | 3 | hallway | Cultist | 80 -> 80 | won | 5 / 5 | 3 | 0.1 s / 0.1 s |  |
| 7 | A0 r1 | 4 | hallway | AcidSlime_S + SpikeSlime_S + AcidSlime_S + SpikeSlime_S + SpikeSlime_S | 80 -> 75 (80 after) | won | 15 / 15 | 8 | 1.1 s / 15.7 s |  |
| 7 | A0 r1 | 5 | hallway | FuzzyLouseDefensive + FuzzyLouseNormal + FuzzyLouseNormal | 80 -> 75 (80 after) | won | 9 / 9 | 6 | 2.1 s / 12.8 s |  |
| 7 | A0 r1 | 7 | hallway | JawWorm + FuzzyLouseNormal | 80 -> 72 (78 after) | won | 10 / 10 | 7 | 0.4 s / 15.5 s |  |
| 7 | A0 r1 | 8 | hallway | FungiBeast + FungiBeast | 78 -> 78 (80 after) | won | 7 / 7 | 5 | 0.2 s / 5.8 s |  |
| 7 | A0 r1 | 10 | elite | Sentry + Sentry + Sentry | 80 -> 74 (80 after) | won | 15 / 15 | 6 | 0.2 s / 13.8 s |  |
| 7 | A0 r1 | 12 | hallway | GremlinWarrior + GremlinWarrior + GremlinTsundere + GremlinWizard | 80 -> 76 (80 after) | won | 13 / 13 | 8 | 1.2 s / 8.1 s |  |
| 7 | A0 r1 | 13 | hallway | FuzzyLouseDefensive + FuzzyLouseNormal + FuzzyLouseNormal | 80 -> 77 (80 after) | won | 5 / 5 | 5 | 0.2 s / 10.2 s |  |
| 7 | A0 r1 | 14 | hallway | AcidSlime_M + Cultist | 80 -> 69 (75 after) | won | 10 / 10 | 7 | 0.3 s / 5.3 s |  |
| 7 | A0 r1 | 16 | boss | SlimeBoss | 80 -> 80 | won | 10 / 10 | 9 | 7.2 s / 14.5 s |  |
| 7 | A0 r1 | 18 | hallway | Byrd + Byrd + Byrd | 80 -> 62 (68 after) | won | - | 0 | - | monster Byrd not loaded |
| 7 | A0 r1 | 19 | hallway | Chosen | 68 -> 58 (64 after) | won | - | 0 | - | monster Chosen not loaded |
| 7 | A0 r1 | 21 | hallway | Centurion + Healer | 49 -> 30 (36 after) | won | - | 0 | - | monster Centurion not loaded |
| 7 | A0 r1 | 22 | hallway | Cultist + Chosen | 36 -> 26 (29 after) | won | - | 0 | - | monster Chosen not loaded |
| 7 | A0 r1 | 23 | elite | GremlinFat + GremlinThief + GremlinLeader | 29 -> 0 | **lost** | - | 0 | - | monster GremlinLeader not loaded |
| 8 | A0 r1 | 1 | hallway | AcidSlime_S + SpikeSlime_M | 80 -> 75 (80 after) | won | 6 / 6 | 3 | 0.0 s / 0.1 s |  |
| 8 | A0 r1 | 2 | hallway | JawWorm | 80 -> 79 (80 after) | won | 10 / 10 | 3 | 0.1 s / 0.1 s |  |
| 8 | A0 r1 | 4 | hallway | FuzzyLouseNormal + FuzzyLouseNormal | 85 -> 78 (84 after) | won | 6 / 6 | 5 | 0.0 s / 1.1 s |  |
| 8 | A0 r1 | 8 | elite | Sentry + Sentry + Sentry | 84 -> 53 (58 after) | won | 24 / 24 | 11 | 0.1 s / 10.9 s |  |
| 8 | A0 r1 | 10 | elite | Lagavulin | 58 -> 27 (33 after) | won | 22 / 22 | 7 | 0.1 s / 0.2 s |  |
| 8 | A0 r1 | 11 | hallway | SpikeSlime_S + AcidSlime_S + SpikeSlime_S + AcidSlime_S + SpikeSlime_S | 33 -> 26 (31 after) | won | 11 / 11 | 3 | 0.3 s / 6.5 s |  |
| 8 | A0 r1 | 12 | hallway | AcidSlime_L | 31 -> 20 (26 after) | won | 6 / 6 | 2 | 0.8 s / 1.4 s | the plan has no pick here |
| 8 | A0 r1 | 16 | boss | TheGuardian | 51 -> 0 | **lost** | 39 / 40 | 19 | 0.1 s / 29.4 s |  |
| 9 | A0 r1 | 1 | hallway | AcidSlime_S + SpikeSlime_M | 80 -> 77 (80 after) | won | 6 / 6 | 3 | 0.0 s / 0.2 s |  |
| 9 | A0 r1 | 2 | hallway | Cultist | 80 -> 74 (80 after) | won | 7 / 7 | 3 | 0.1 s / 0.5 s |  |
| 9 | A0 r1 | 3 | hallway | FuzzyLouseNormal + FuzzyLouseNormal | 80 -> 76 (80 after) | won | 10 / 10 | 4 | 0.4 s / 1.1 s |  |
| 9 | A0 r1 | 4 | hallway | SlaverRed | 80 -> 77 (80 after) | won | 15 / 15 | 6 | 0.1 s / 0.2 s |  |
| 9 | A0 r1 | 5 | hallway | AcidSlime_M + Looter | 80 -> 62 (68 after) | won | 14 / 14 | 6 | 1.1 s / 6.8 s |  |
| 9 | A0 r1 | 8 | hallway | AcidSlime_L | 68 -> 60 (66 after) | won | 19 / 19 | 8 | 0.5 s / 3.3 s |  |
| 9 | A0 r1 | 10 | hallway | FuzzyLouseDefensive + FuzzyLouseDefensive + FuzzyLouseDefensive | 66 -> 66 (72 after) | won | 10 / 10 | 4 | 13.0 s / 29.9 s |  |
| 9 | A0 r1 | 11 | hallway | AcidSlime_M + Cultist | 72 -> 72 (78 after) | won | 13 / 13 | 4 | 1.4 s / 3.1 s |  |
| 9 | A0 r1 | 13 | hallway | SlaverBlue | 78 -> 76 (80 after) | won | 9 / 9 | 4 | 0.2 s / 0.3 s |  |
| 9 | A0 r1 | 14 | hallway | GremlinFat + GremlinThief + GremlinWizard + GremlinTsundere | 80 -> 75 (80 after) | won | 19 / 19 | 7 | 2.3 s / 11.2 s |  |
| 9 | A0 r1 | 16 | boss | TheGuardian | 80 -> 55 (61 after) | won | 26 / 26 | 13 | 0.2 s / 2.8 s |  |
| 9 | A0 r1 | 18 | hallway | SphericGuardian | 80 -> 60 (66 after) | won | - | 0 | - | monster SphericGuardian not loaded |
| 9 | A0 r1 | 19 | hallway | Byrd + Byrd + Byrd | 66 -> 50 (56 after) | won | - | 0 | - | monster Byrd not loaded |
| 9 | A0 r1 | 24 | hallway | SnakePlant | 56 -> 48 (54 after) | won | - | 0 | - | monster SnakePlant not loaded |
| 9 | A0 r1 | 27 | hallway | Cultist + Chosen | 64 -> 12 (18 after) | won | - | 0 | - | monster Chosen not loaded |
| 9 | A0 r1 | 29 | hallway | Cultist + Cultist + Cultist | 45 -> 38 (44 after) | won | 7 / 7 | 7 | 10.8 s / 19.1 s |  |
| 9 | A0 r1 | 30 | hallway | Centurion + Healer | 44 -> 31 (37 after) | won | - | 0 | - | monster Centurion not loaded |
| 9 | A0 r1 | 31 | hallway | Cultist + Chosen | 37 -> 0 | **lost** | - | 0 | - | monster Chosen not loaded |
| 10 | A0 r1 | 1 | hallway | JawWorm | 80 -> 74 (80 after) | won | 6 / 6 | 3 | 0.1 s / 0.1 s |  |
| 10 | A0 r1 | 3 | hallway | Cultist | 80 -> 80 | won | 8 / 8 | 6 | 0.2 s / 9.2 s |  |
| 10 | A0 r1 | 4 | hallway | AcidSlime_S + SpikeSlime_M | 80 -> 75 (80 after) | won | 9 / 9 | 4 | 0.1 s / 0.3 s |  |
| 10 | A0 r1 | 5 | hallway | FungiBeast + FungiBeast | 80 -> 74 (80 after) | won | 7 / 8 | 4 | 0.5 s / 9.0 s |  |
| 10 | A0 r1 | 7 | hallway | SlaverRed | 80 -> 69 (75 after) | won | 11 / 11 | 4 | 0.1 s / 0.6 s |  |
| 10 | A0 r1 | 10 | hallway | SpikeSlime_L | 75 -> 75 (80 after) | won | 11 / 11 | 4 | 0.6 s / 1.3 s |  |
| 10 | A0 r1 | 11 | hallway | SlaverBlue | 80 -> 76 (80 after) | won | 9 / 9 | 3 | 0.3 s / 4.7 s |  |
| 10 | A0 r1 | 12 | elite | Sentry + Sentry + Sentry | 80 -> 54 (60 after) | won | 12 / 12 | 6 | 0.3 s / 10.0 s |  |
| 10 | A0 r1 | 13 | hallway | FungiBeast + FungiBeast | 60 -> 54 (60 after) | won | 6 / 6 | 2 | 3.0 s / 5.8 s |  |
| 10 | A0 r1 | 14 | hallway | Looter | 60 -> 56 (62 after) | won | 4 / 4 | 3 | 0.1 s / 7.1 s |  |
| 10 | A0 r1 | 16 | boss | SlimeBoss | 62 -> 62 (68 after) | won | 17 / 17 | 7 | 0.3 s / 9.1 s |  |
| 10 | A0 r1 | 18 | hallway | SphericGuardian | 80 -> 76 (80 after) | won | - | 0 | - | monster SphericGuardian not loaded |
| 10 | A0 r1 | 19 | hallway | Shelled Parasite | 80 -> 51 (57 after) | won | - | 0 | - | monster Shelled Parasite not loaded |
| 10 | A0 r1 | 20 | hallway | Sentry + SphericGuardian | 57 -> 16 (22 after) | won | - | 0 | - | monster SphericGuardian not loaded |
| 10 | A0 r1 | 21 | hallway | Cultist + Chosen | 22 -> 0 | **lost** | - | 0 | - | monster Chosen not loaded |
| 11 | A0 r1 | 1 | hallway | SpikeSlime_S + AcidSlime_M | 80 -> 80 | won | 4 / 4 | 2 | 0.1 s / 0.1 s |  |
| 11 | A0 r1 | 3 | hallway | FuzzyLouseNormal + FuzzyLouseDefensive | 80 -> 80 | won | 6 / 6 | 2 | 0.2 s / 0.3 s |  |
| 11 | A0 r1 | 4 | hallway | Cultist | 80 -> 79 (80 after) | won | 11 / 11 | 4 | 0.0 s / 0.0 s |  |
| 11 | A0 r1 | 5 | hallway | Looter | 80 -> 75 (80 after) | won | 8 / 8 | 4 | 0.1 s / 5.1 s |  |
| 11 | A0 r1 | 6 | elite | Sentry + Sentry + Sentry | 80 -> 63 (69 after) | won | 15 / 15 | 6 | 0.1 s / 0.5 s |  |
| 11 | A0 r1 | 8 | hallway | FungiBeast + FungiBeast | 69 -> 60 (66 after) | won | 8 / 8 | 3 | 0.1 s / 0.5 s |  |
| 11 | A0 r1 | 11 | hallway | FungiBeast + FungiBeast + FungiBeast | 66 -> 64 (70 after) | won | 4 / 4 | 2 | 2.0 s / 4.0 s |  |
| 11 | A0 r1 | 13 | hallway | GremlinWarrior + GremlinThief + GremlinWarrior + GremlinTsundere | 70 -> 68 (74 after) | won | 10 / 10 | 5 | 6.8 s / 17.9 s |  |
| 11 | A0 r1 | 16 | boss | SlimeBoss | 74 -> 39 (57 after) | won | 12 / 12 | 7 | 9.8 s / 23.7 s |  |
| 11 | A0 r1 | 18 | hallway | Shelled Parasite | 80 -> 31 (49 after) | won | - | 0 | - | monster Shelled Parasite not loaded |
| 11 | A0 r1 | 19 | hallway | Chosen | 49 -> 43 (49 after) | won | - | 0 | - | monster Chosen not loaded |
| 11 | A0 r1 | 20 | hallway | Snecko | 49 -> 37 (50 after) | won | - | 0 | - | monster Snecko not loaded |
| 11 | A0 r1 | 21 | hallway | Shelled Parasite + FungiBeast | 50 -> 0 | **lost** | - | 0 | - | monster Shelled Parasite not loaded |
| 12 | A0 r1 | 1 | hallway | FuzzyLouseNormal + FuzzyLouseNormal | 80 -> 78 (80 after) | won | 4 / 4 | 2 | 0.1 s / 0.1 s |  |
| 12 | A0 r1 | 3 | hallway | AcidSlime_S + SpikeSlime_M | 85 -> 82 (85 after) | won | 8 / 8 | 4 | 0.0 s / 0.1 s |  |
| 12 | A0 r1 | 4 | hallway | JawWorm | 85 -> 82 (85 after) | won | 9 / 9 | 3 | 0.1 s / 0.2 s |  |
| 12 | A0 r1 | 5 | hallway | FuzzyLouseDefensive + FuzzyLouseNormal + FuzzyLouseNormal | 85 -> 83 (85 after) | won | 8 / 8 | 3 | 0.5 s / 9.7 s |  |
| 12 | A0 r1 | 11 | elite | Lagavulin | 85 -> 73 (79 after) | won | 20 / 22 | 6 | 0.0 s / 0.1 s |  |
| 12 | A0 r1 | 12 | hallway | SlaverBlue | 79 -> 72 (78 after) | won | 8 / 8 | 7 | 0.4 s / 24.7 s |  |
| 12 | A0 r1 | 13 | hallway | SpikeSlime_L | 78 -> 75 (81 after) | won | 6 / 6 | 7 | 0.5 s / 52.6 s |  |
| 12 | A0 r1 | 14 | hallway | SpikeSlime_S + SpikeSlime_S + AcidSlime_S + SpikeSlime_S + AcidSlime_S | 81 -> 84 (85 after) | won | 12 / 13 | 4 | 1.2 s / 22.2 s |  |
| 12 | A0 r1 | 16 | boss | SlimeBoss | 85 -> 81 (85 after) | won | 20 / 21 | 7 | 0.5 s / 11.4 s |  |
| 12 | A0 r1 | 18 | hallway | Looter + Mugger | 85 -> 56 (62 after) | won | - | 0 | - | monster Mugger not loaded |
| 12 | A0 r1 | 20 | hallway | Byrd + Byrd + Byrd | 62 -> 20 (26 after) | won | - | 0 | - | monster Byrd not loaded |
| 12 | A0 r1 | 21 | hallway | Snecko | 26 -> 5 (11 after) | won | - | 0 | - | monster Snecko not loaded |
| 12 | A0 r1 | 22 | hallway | Cultist + Chosen | 11 -> 0 | **lost** | - | 0 | - | monster Chosen not loaded |
| 13 | A0 r1 | 1 | hallway | FuzzyLouseDefensive + FuzzyLouseDefensive | 80 -> 73 (79 after) | won | 5 / 5 | 2 | 0.1 s / 0.1 s |  |
| 13 | A0 r1 | 2 | hallway | AcidSlime_S + SpikeSlime_M | 79 -> 77 (80 after) | won | 11 / 11 | 4 | 0.0 s / 0.1 s |  |
| 13 | A0 r1 | 3 | hallway | JawWorm | 80 -> 79 (80 after) | won | 7 / 7 | 3 | 0.1 s / 0.2 s |  |
| 13 | A0 r1 | 5 | hallway | Looter | 80 -> 75 (80 after) | won | 9 / 9 | 4 | 0.5 s / 1.4 s |  |
| 13 | A0 r1 | 6 | elite | Sentry + Sentry + Sentry | 80 -> 13 (19 after) | won | 35 / 35 | 15 | 0.0 s / 0.5 s |  |
| 13 | A0 r1 | 10 | hallway | FungiBeast + FungiBeast | 43 -> 30 (36 after) | won | 10 / 10 | 6 | 5.3 s / 9.3 s |  |
| 13 | A0 r1 | 11 | hallway | SlaverRed | 36 -> 23 (29 after) | won | 4 / 4 | 5 | 14.0 s / 19.2 s |  |
| 13 | A0 r1 | 12 | hallway | FuzzyLouseDefensive + FuzzyLouseDefensive + FuzzyLouseDefensive | 29 -> 29 (35 after) | won | 8 / 8 | 4 | 6.4 s / 14.6 s |  |
| 13 | A0 r1 | 13 | hallway | Looter | 35 -> 33 (39 after) | won | 13 / 13 | 4 | 0.2 s / 0.5 s |  |
| 13 | A0 r1 | 14 | hallway | AcidSlime_M + Cultist | 39 -> 34 (40 after) | won | 21 / 21 | 6 | 1.2 s / 13.6 s |  |
| 13 | A0 r1 | 16 | boss | TheGuardian | 64 -> 40 (46 after) | won | 48 / 49 | 16 | 0.2 s / 17.7 s |  |
| 13 | A0 r1 | 18 | hallway | Shelled Parasite | 80 -> 18 (30 after) | won | - | 0 | - | monster Shelled Parasite not loaded |
| 13 | A0 r1 | 21 | hallway | Chosen | 56 -> 0 | **lost** | - | 0 | - | monster Chosen not loaded |
| 14 | A0 r1 | 1 | hallway | Cultist | 80 -> 74 (80 after) | won | 8 / 8 | 3 | 0.0 s / 0.1 s |  |
| 14 | A0 r1 | 2 | hallway | SpikeSlime_S + AcidSlime_M | 80 -> 70 (76 after) | won | 13 / 13 | 5 | 0.0 s / 0.0 s |  |
| 14 | A0 r1 | 3 | hallway | FuzzyLouseNormal + FuzzyLouseDefensive | 76 -> 71 (77 after) | won | 5 / 5 | 3 | 0.1 s / 0.1 s |  |
| 14 | A0 r1 | 4 | hallway | FungiBeast + FungiBeast | 77 -> 69 (75 after) | won | 9 / 9 | 5 | 0.2 s / 1.3 s |  |
| 14 | A0 r1 | 5 | hallway | SlaverRed | 75 -> 72 (78 after) | won | 8 / 8 | 7 | 0.1 s / 1.1 s |  |
| 14 | A0 r1 | 6 | hallway | FuzzyLouseDefensive + FuzzyLouseDefensive + FuzzyLouseDefensive | 78 -> 80 | won | 10 / 10 | 6 | 0.7 s / 16.6 s |  |
| 14 | A0 r1 | 7 | hallway | SpikeSlime_L | 80 -> 70 (76 after) | won | 15 / 15 | 11 | 0.2 s / 1.4 s |  |
| 14 | A0 r1 | 8 | elite | Sentry + Sentry + Sentry | 76 -> 30 (36 after) | won | 29 / 29 | 17 | 0.1 s / 1.2 s |  |
| 14 | A0 r1 | 11 | hallway | GremlinThief + GremlinTsundere + GremlinWizard + GremlinWarrior | 36 -> 36 (42 after) | won | 10 / 11 | 10 | 0.6 s / 12.3 s |  |
| 14 | A0 r1 | 14 | hallway | FuzzyLouseDefensive + Looter | 66 -> 64 (70 after) | won | 15 / 15 | 6 | 1.0 s / 9.6 s |  |
| 14 | A0 r1 | 16 | boss | TheGuardian | 70 -> 34 (39 after) | won | 28 / 28 | 19 | 0.2 s / 1.7 s |  |
| 14 | A0 r1 | 18 | hallway | SphericGuardian | 80 -> 52 (64 after) | won | - | 0 | - | monster SphericGuardian not loaded |
| 14 | A0 r1 | 20 | hallway | Shelled Parasite | 64 -> 15 (27 after) | won | - | 0 | - | monster Shelled Parasite not loaded |
| 14 | A0 r1 | 21 | hallway | Cultist + Chosen | 27 -> 1 (13 after) | won | - | 0 | - | monster Chosen not loaded |
| 14 | A0 r1 | 22 | hallway | Centurion + Healer | 13 -> 0 | **lost** | - | 0 | - | monster Centurion not loaded |
| 15 | A0 r1 | 1 | hallway | FuzzyLouseNormal + FuzzyLouseNormal | 80 -> 75 (80 after) | won | 4 / 4 | 2 | 0.0 s / 0.1 s |  |
| 15 | A0 r1 | 2 | hallway | JawWorm | 80 -> 77 (80 after) | won | 8 / 8 | 3 | 0.1 s / 1.1 s |  |
| 15 | A0 r1 | 5 | hallway | Cultist | 80 -> 79 (80 after) | won | 6 / 6 | 3 | 0.1 s / 0.1 s |  |
| 15 | A0 r1 | 7 | hallway | AcidSlime_L | 80 -> 78 (80 after) | won | 19 / 19 | 10 | 1.6 s / 11.9 s |  |
| 15 | A0 r1 | 8 | hallway | FungiBeast + FungiBeast | 80 -> 80 | won | 8 / 8 | 4 | 9.2 s / 10.1 s |  |
| 15 | A0 r1 | 11 | hallway | SlaverBlue | 80 -> 73 (79 after) | won | 5 / 5 | 2 | 4.8 s / 5.8 s |  |
| 15 | A0 r1 | 12 | hallway | AcidSlime_L | 79 -> 73 (79 after) | won | 14 / 14 | 6 | 8.0 s / 10.6 s |  |
| 15 | A0 r1 | 13 | hallway | GremlinTsundere + GremlinFat + GremlinThief + GremlinWarrior | 79 -> 79 (80 after) | won | 9 / 9 | 6 | 0.3 s / 12.8 s |  |
| 15 | A0 r1 | 14 | hallway | FungiBeast + FuzzyLouseNormal | 80 -> 79 (80 after) | won | 5 / 6 | 5 | 5.2 s / 10.2 s |  |
| 15 | A0 r1 | 16 | boss | TheGuardian | 80 -> 45 (48 after) | won | 43 / 44 | 22 | 0.5 s / 6.7 s |  |
| 15 | A0 r1 | 18 | hallway | SphericGuardian | 80 -> 18 (24 after) | won | - | 0 | - | monster SphericGuardian not loaded |
| 15 | A0 r1 | 19 | hallway | Looter + Mugger | 24 -> 1 (7 after) | won | - | 0 | - | monster Mugger not loaded |
| 15 | A0 r1 | 20 | hallway | Centurion + Healer | 7 -> 0 | **lost** | - | 0 | - | monster Centurion not loaded |
| 16 | A0 r1 | 1 | hallway | AcidSlime_S + SpikeSlime_M | 80 -> 77 (80 after) | won | 6 / 6 | 3 | 0.0 s / 0.1 s |  |
| 16 | A0 r1 | 2 | hallway | JawWorm | 80 -> 79 (80 after) | won | 7 / 7 | 3 | 0.1 s / 0.2 s |  |
| 16 | A0 r1 | 3 | hallway | Cultist | 80 -> 77 (80 after) | won | 11 / 11 | 6 | 0.4 s / 3.1 s |  |
| 16 | A0 r1 | 4 | hallway | SpikeSlime_M + Cultist | 80 -> 74 (80 after) | won | 15 / 15 | 6 | 1.5 s / 3.3 s |  |
| 16 | A0 r1 | 5 | hallway | FungiBeast + SpikeSlime_M | 80 -> 74 (80 after) | won | 11 / 11 | 5 | 0.5 s / 0.6 s |  |
| 16 | A0 r1 | 7 | hallway | SlaverRed | 80 -> 70 (76 after) | won | 6 / 6 | 3 | 0.1 s / 0.2 s |  |
| 16 | A0 r1 | 8 | elite | GremlinNob | 76 -> 62 (68 after) | won | 11 / 11 | 4 | 0.1 s / 0.1 s |  |
| 16 | A0 r1 | 11 | hallway | SpikeSlime_L | 68 -> 68 (74 after) | won | 8 / 8 | 4 | 0.3 s / 0.9 s |  |
| 16 | A0 r1 | 14 | hallway | FuzzyLouseNormal + FuzzyLouseNormal + FuzzyLouseDefensive | 74 -> 77 (83 after) | won | 7 / 8 | 8 | 2.5 s / 14.2 s |  |
| 16 | A0 r1 | 16 | boss | TheGuardian | 83 -> 0 | **lost** | 8 / 8 | 5 | 0.3 s / 0.6 s | card gen:Blood for Blood+ not in the game's hand |
| 17 | A0 r1 | 1 | hallway | AcidSlime_S + SpikeSlime_M | 80 -> 80 | won | 9 / 9 | 4 | 0.0 s / 0.1 s |  |
| 17 | A0 r1 | 2 | hallway | Cultist | 80 -> 74 (80 after) | won | 7 / 7 | 3 | 0.0 s / 0.0 s |  |
| 17 | A0 r1 | 3 | hallway | FuzzyLouseNormal + FuzzyLouseDefensive | 80 -> 74 (80 after) | won | 4 / 4 | 2 | 0.1 s / 0.1 s |  |
| 17 | A0 r1 | 4 | hallway | SpikeSlime_S + SpikeSlime_S + AcidSlime_S + SpikeSlime_S + AcidSlime_S | 80 -> 70 (76 after) | won | 23 / 23 | 8 | 0.3 s / 5.4 s |  |
| 17 | A0 r1 | 6 | elite | Lagavulin | 76 -> 16 (22 after) | won | 21 / 21 | 10 | 0.0 s / 0.1 s |  |
| 17 | A0 r1 | 7 | hallway | SpikeSlime_L | 22 -> 17 (23 after) | won | 15 / 15 | 7 | 0.2 s / 1.9 s |  |
| 17 | A0 r1 | 8 | hallway | JawWorm + FuzzyLouseDefensive | 23 -> 22 (28 after) | won | 14 / 14 | 6 | 0.1 s / 8.7 s |  |
| 17 | A0 r1 | 11 | hallway | FungiBeast + FungiBeast | 28 -> 24 (30 after) | won | 9 / 9 | 6 | 0.3 s / 11.0 s |  |
| 17 | A0 r1 | 12 | hallway | SlaverBlue | 30 -> 16 (22 after) | won | 15 / 15 | 5 | 0.1 s / 0.1 s |  |
| 17 | A0 r1 | 13 | hallway | SpikeSlime_L | 22 -> 22 (28 after) | won | 8 / 8 | 3 | 0.5 s / 1.0 s |  |
| 17 | A0 r1 | 14 | hallway | FungiBeast + FungiBeast | 28 -> 22 (28 after) | won | 5 / 5 | 4 | 5.9 s / 16.6 s |  |
| 17 | A0 r1 | 16 | boss | Hexaghost | 52 -> 27 (33 after) | won | 33 / 33 | 14 | 3.5 s / 8.1 s |  |
| 17 | A0 r1 | 18 | hallway | SphericGuardian | 80 -> 49 (45 after) | won | - | 0 | - | monster SphericGuardian not loaded |
| 17 | A0 r1 | 19 | hallway | Shelled Parasite | 45 -> 1 (7 after) | won | - | 0 | - | monster Shelled Parasite not loaded |
| 17 | A0 r1 | 21 | hallway | SnakePlant | 33 -> 0 | **lost** | - | 0 | - | monster SnakePlant not loaded |
| 18 | A0 r1 | 1 | hallway | FuzzyLouseNormal + FuzzyLouseNormal | 80 -> 73 (79 after) | won | 9 / 9 | 5 | 0.0 s / 0.1 s |  |
| 18 | A0 r1 | 2 | hallway | AcidSlime_S + SpikeSlime_M | 79 -> 79 (80 after) | won | 60 / 60 | 28 | 0.0 s / 0.1 s |  |
| 18 | A0 r1 | 4 | hallway | JawWorm | 80 -> 74 (80 after) | won | 12 / 12 | 5 | 0.0 s / 0.0 s |  |
| 18 | A0 r1 | 5 | hallway | AcidSlime_L | 80 -> 67 (73 after) | won | 20 / 20 | 7 | 0.2 s / 1.3 s |  |
| 18 | A0 r1 | 6 | elite | Lagavulin | 73 -> 42 (48 after) | won | 27 / 27 | 14 | 0.0 s / 0.2 s |  |
| 18 | A0 r1 | 7 | hallway | FungiBeast + FungiBeast | 48 -> 43 (49 after) | won | 6 / 6 | 4 | 0.2 s / 2.1 s |  |
| 18 | A0 r1 | 8 | hallway | FungiBeast + AcidSlime_M | 49 -> 40 (46 after) | won | 12 / 12 | 8 | 3.0 s / 12.2 s |  |
| 18 | A0 r1 | 10 | hallway | Looter | 46 -> 44 (50 after) | won | 6 / 6 | 3 | 0.2 s / 0.2 s |  |
| 18 | A0 r1 | 11 | hallway | FuzzyLouseDefensive + SlaverBlue | 50 -> 36 (42 after) | won | 14 / 14 | 14 | 1.1 s / 17.8 s |  |
| 18 | A0 r1 | 12 | hallway | SlaverRed | 42 -> 42 (48 after) | won | 8 / 8 | 7 | 0.1 s / 0.5 s |  |
| 18 | A0 r1 | 13 | hallway | AcidSlime_L | 48 -> 48 (54 after) | won | 23 / 23 | 13 | 1.4 s / 7.4 s |  |
| 18 | A0 r1 | 16 | boss | TheGuardian | 78 -> 47 (53 after) | won | 26 / 26 | 13 | 0.2 s / 4.4 s |  |
| 18 | A0 r1 | 18 | hallway | Byrd + Byrd + Byrd | 80 -> 0 | **lost** | - | 0 | - | monster Byrd not loaded |
| 19 | A0 r1 | 1 | hallway | FuzzyLouseNormal + FuzzyLouseNormal | 80 -> 80 | won | 8 / 8 | 3 | 0.1 s / 0.1 s |  |
| 19 | A0 r1 | 3 | hallway | JawWorm | 80 -> 74 (80 after) | won | 7 / 7 | 4 | 0.1 s / 5.0 s |  |
| 19 | A0 r1 | 4 | hallway | SpikeSlime_S + AcidSlime_M | 80 -> 75 (80 after) | won | 8 / 8 | 3 | 0.7 s / 1.5 s |  |
| 19 | A0 r1 | 5 | hallway | SlaverBlue | 80 -> 69 (75 after) | won | 11 / 11 | 4 | 0.2 s / 0.3 s |  |
| 19 | A0 r1 | 7 | hallway | SlaverRed | 75 -> 67 (73 after) | won | 9 / 9 | 4 | 0.1 s / 0.6 s |  |
| 19 | A0 r1 | 8 | hallway | GremlinTsundere + GremlinFat + GremlinWarrior + GremlinWarrior | 73 -> 66 (72 after) | won | 9 / 9 | 7 | 2.2 s / 5.9 s |  |
| 19 | A0 r1 | 12 | hallway | SpikeSlime_S + SpikeSlime_S + AcidSlime_S + SpikeSlime_S + AcidSlime_S | 72 -> 60 (66 after) | won | 12 / 12 | 8 | 0.5 s / 10.5 s |  |
| 19 | A0 r1 | 14 | hallway | Looter | 66 -> 66 (72 after) | won | 7 / 7 | 3 | 0.5 s / 0.8 s |  |
| 19 | A0 r1 | 16 | boss | Hexaghost | 72 -> 7 (13 after) | won | 24 / 24 | 11 | 0.5 s / 5.3 s |  |
| 19 | A0 r1 | 18 | hallway | Byrd + Byrd + Byrd | 80 -> 48 (54 after) | won | - | 0 | - | monster Byrd not loaded |
| 19 | A0 r1 | 20 | hallway | SphericGuardian | 54 -> 7 (13 after) | won | - | 0 | - | monster SphericGuardian not loaded |
| 19 | A0 r1 | 21 | hallway | Centurion + Healer | 13 -> 0 | **lost** | - | 0 | - | monster Centurion not loaded |
| 20 | A0 r1 | 1 | hallway | Cultist | 80 -> 74 (80 after) | won | 6 / 6 | 3 | 0.0 s / 0.1 s |  |
| 20 | A0 r1 | 2 | hallway | JawWorm | 80 -> 79 (80 after) | won | 9 / 9 | 3 | 0.2 s / 0.3 s |  |
| 20 | A0 r1 | 3 | hallway | FuzzyLouseNormal + FuzzyLouseNormal | 80 -> 75 (80 after) | won | 7 / 7 | 3 | 0.1 s / 1.6 s |  |
| 20 | A0 r1 | 4 | hallway | GremlinFat + GremlinWarrior + GremlinThief + GremlinTsundere | 80 -> 65 (71 after) | won | 21 / 21 | 11 | 2.4 s / 17.0 s |  |
| 20 | A0 r1 | 5 | hallway | SlaverRed | 71 -> 65 (71 after) | won | 11 / 11 | 4 | 0.2 s / 0.5 s |  |
| 20 | A0 r1 | 7 | hallway | SpikeSlime_S + AcidSlime_S + AcidSlime_S + SpikeSlime_S + SpikeSlime_S | 71 -> 65 (71 after) | won | 13 / 13 | 5 | 8.0 s / 24.9 s |  |
| 20 | A0 r1 | 10 | hallway | SpikeSlime_M + Looter | 71 -> 65 (71 after) | won | 12 / 12 | 5 | 0.2 s / 19.9 s |  |
| 20 | A0 r1 | 11 | hallway | Looter | 71 -> 64 (70 after) | won | 11 / 11 | 4 | 0.1 s / 0.9 s |  |
| 20 | A0 r1 | 13 | hallway | SlaverRed | 70 -> 67 (73 after) | won | 7 / 7 | 2 | 1.0 s / 1.8 s |  |
| 20 | A0 r1 | 14 | hallway | JawWorm + AcidSlime_M | 73 -> 64 (70 after) | won | 13 / 13 | 6 | 4.1 s / 17.7 s |  |
| 20 | A0 r1 | 16 | boss | TheGuardian | 70 -> 62 (68 after) | won | 34 / 34 | 13 | 0.1 s / 0.3 s |  |
| 20 | A0 r1 | 18 | hallway | SphericGuardian | 80 -> 47 (53 after) | won | - | 0 | - | monster SphericGuardian not loaded |
| 20 | A0 r1 | 19 | hallway | Looter + Mugger | 53 -> 34 (40 after) | won | - | 0 | - | monster Mugger not loaded |
| 20 | A0 r1 | 20 | hallway | Centurion + Healer | 40 -> 30 (36 after) | won | - | 0 | - | monster Centurion not loaded |
| 20 | A0 r1 | 21 | hallway | Sentry + SphericGuardian | 36 -> 0 | **lost** | - | 0 | - | monster SphericGuardian not loaded |
| 21 | A0 r1 | 1 | hallway | JawWorm | 88 -> 82 (88 after) | won | 13 / 13 | 5 | 0.1 s / 0.1 s |  |
| 21 | A0 r1 | 2 | hallway | Cultist | 88 -> 86 (88 after) | won | 9 / 9 | 3 | 0.0 s / 0.0 s |  |
| 21 | A0 r1 | 3 | hallway | SpikeSlime_S + AcidSlime_M | 88 -> 83 (88 after) | won | 11 / 11 | 4 | 0.1 s / 0.4 s |  |
| 21 | A0 r1 | 6 | elite | Lagavulin | 88 -> 62 (68 after) | won | 31 / 31 | 13 | 0.3 s / 5.1 s |  |
| 21 | A0 r1 | 7 | hallway | SlaverBlue | 68 -> 56 (62 after) | won | 12 / 12 | 6 | 0.2 s / 3.0 s |  |
| 21 | A0 r1 | 8 | hallway | AcidSlime_L | 62 -> 65 (71 after) | won | 38 / 38 | 14 | 4.2 s / 16.2 s |  |
| 21 | A0 r1 | 10 | elite | Sentry + Sentry + Sentry | 73 -> 39 (45 after) | won | 31 / 31 | 12 | 0.4 s / 7.3 s |  |
| 21 | A0 r1 | 11 | hallway | Looter | 47 -> 42 (48 after) | won | 7 / 7 | 3 | 0.1 s / 1.0 s |  |
| 21 | A0 r1 | 12 | hallway | SlaverBlue | 50 -> 43 (49 after) | won | 12 / 12 | 6 | 0.4 s / 2.7 s |  |
| 21 | A0 r1 | 14 | hallway | GremlinWizard + GremlinThief + GremlinFat + GremlinWarrior | 51 -> 56 (50 after) | won | 3 / 3 | 4 | 10.2 s / 17.7 s |  |
| 21 | A0 r1 | 16 | boss | Hexaghost | 78 -> 29 (35 after) | won | 41 / 42 | 14 | 0.3 s / 12.5 s |  |
| 21 | A0 r1 | 18 | hallway | SphericGuardian | 88 -> 63 (69 after) | won | - | 0 | - | monster SphericGuardian not loaded |
| 22 | A0 r1 | 1 | hallway | JawWorm | 80 -> 72 (78 after) | won | 10 / 10 | 5 | 0.3 s / 3.8 s |  |
| 22 | A0 r1 | 2 | hallway | FuzzyLouseNormal + FuzzyLouseNormal | 78 -> 77 (80 after) | won | 6 / 6 | 3 | 5.7 s / 6.1 s |  |
| 22 | A0 r1 | 3 | hallway | Cultist | 80 -> 74 (80 after) | won | 8 / 8 | 5 | 0.1 s / 1.7 s |  |
| 22 | A0 r1 | 4 | hallway | AcidSlime_S + SpikeSlime_S + SpikeSlime_S + AcidSlime_S + SpikeSlime_S | 80 -> 72 (78 after) | won | 8 / 8 | 5 | 7.7 s / 16.9 s |  |
| 22 | A0 r1 | 5 | hallway | FuzzyLouseDefensive + FuzzyLouseNormal + FuzzyLouseNormal | 78 -> 78 (80 after) | won | 4 / 4 | 4 | 11.7 s / 13.2 s |  |
| 22 | A0 r1 | 6 | hallway | GremlinThief + GremlinWarrior + GremlinThief + GremlinTsundere | 80 -> 67 (73 after) | won | 22 / 22 | 15 | 0.2 s / 11.7 s |  |
| 22 | A0 r1 | 7 | hallway | SlaverRed | 73 -> 73 (79 after) | won | 8 / 9 | 6 | 4.6 s / 15.9 s |  |
| 22 | A0 r1 | 8 | hallway | AcidSlime_M + Looter | 79 -> 72 (78 after) | won | 14 / 14 | 10 | 9.1 s / 21.7 s |  |
| 22 | A0 r1 | 10 | elite | Sentry + Sentry + Sentry | 78 -> 64 (70 after) | won | 12 / 12 | 9 | 0.4 s / 20.8 s |  |
| 22 | A0 r1 | 12 | hallway | FungiBeast + FungiBeast | 70 -> 58 (64 after) | won | 10 / 10 | 11 | 2.5 s / 17.0 s |  |
| 22 | A0 r1 | 13 | hallway | SpikeSlime_L | 64 -> 64 (70 after) | won | 15 / 15 | 12 | 1.8 s / 14.2 s |  |
| 22 | A0 r1 | 14 | hallway | FungiBeast + FungiBeast + FungiBeast | 70 -> 11 (17 after) | won | 1 / 1 | 3 | 24.5 s / 29.4 s | card Dual Wield not loaded |
| 22 | A0 r1 | 16 | boss | TheGuardian | 41 -> 29 (35 after) | won | 28 / 28 | 15 | 0.8 s / 9.9 s |  |
| 23 | A0 r1 | 1 | hallway | JawWorm | 80 -> 72 (78 after) | won | 7 / 7 | 3 | 0.0 s / 0.1 s |  |
| 23 | A0 r1 | 3 | hallway | Cultist | 78 -> 77 (80 after) | won | 6 / 6 | 6 | 7.1 s / 16.7 s |  |
| 23 | A0 r1 | 4 | hallway | FuzzyLouseNormal + FuzzyLouseDefensive | 80 -> 79 (80 after) | won | 6 / 6 | 2 | 1.9 s / 3.6 s |  |
| 23 | A0 r1 | 5 | hallway | Looter | 80 -> 74 (80 after) | won | 6 / 6 | 4 | 0.3 s / 3.2 s |  |
| 23 | A0 r1 | 6 | elite | GremlinNob | 80 -> 66 (72 after) | won | 7 / 7 | 5 | 1.0 s / 10.5 s |  |
| 23 | A0 r1 | 7 | hallway | FungiBeast + FungiBeast | 72 -> 63 (69 after) | won | 9 / 10 | 10 | 1.0 s / 14.4 s |  |
| 23 | A0 r1 | 8 | hallway | FuzzyLouseDefensive + Looter | 69 -> 59 (65 after) | won | 18 / 20 | 18 | 10.3 s / 17.8 s |  |
| 23 | A0 r1 | 11 | hallway | Looter | 65 -> 61 (67 after) | won | 7 / 8 | 6 | 0.4 s / 19.0 s |  |
| 23 | A0 r1 | 12 | hallway | SlaverRed | 67 -> 62 (68 after) | won | 6 / 7 | 8 | 8.0 s / 17.4 s |  |
| 23 | A0 r1 | 13 | hallway | SlaverBlue | 68 -> 62 (68 after) | won | 15 / 15 | 12 | 9.1 s / 21.4 s |  |
| 23 | A0 r1 | 16 | boss | TheGuardian | 68 -> 40 (58 after) | won | 50 / 55 | 42 | 5.9 s / 15.5 s |  |
| 24 | A0 r1 | 1 | hallway | Cultist | 80 -> 74 (80 after) | won | 5 / 5 | 3 | 0.0 s / 0.0 s |  |
| 24 | A0 r1 | 2 | hallway | SpikeSlime_S + AcidSlime_M | 80 -> 77 (80 after) | won | 9 / 9 | 4 | 0.5 s / 1.0 s |  |
| 24 | A0 r1 | 3 | hallway | JawWorm | 80 -> 72 (78 after) | won | 9 / 9 | 4 | 0.1 s / 0.5 s |  |
| 24 | A0 r1 | 4 | hallway | FuzzyLouseDefensive + FuzzyLouseDefensive + FuzzyLouseDefensive | 78 -> 69 (75 after) | won | 22 / 22 | 9 | 0.3 s / 8.9 s |  |
| 24 | A0 r1 | 5 | hallway | FungiBeast + FungiBeast | 75 -> 74 (80 after) | won | 10 / 10 | 4 | 1.0 s / 2.3 s |  |
| 24 | A0 r1 | 6 | elite | GremlinNob | 80 -> 74 (80 after) | won | 8 / 8 | 5 | 0.6 s / 13.7 s |  |
| 24 | A0 r1 | 8 | hallway | JawWorm + AcidSlime_M | 85 -> 73 (79 after) | won | 21 / 21 | 8 | 0.7 s / 4.6 s |  |
| 24 | A0 r1 | 10 | hallway | FuzzyLouseNormal + FuzzyLouseNormal + FuzzyLouseNormal | 79 -> 79 (85 after) | won | 7 / 7 | 7 | 0.3 s / 17.5 s |  |
| 24 | A0 r1 | 11 | hallway | SlaverBlue | 85 -> 84 (85 after) | won | 5 / 5 | 2 | 0.4 s / 0.6 s |  |
| 24 | A0 r1 | 12 | hallway | FungiBeast + FungiBeast | 85 -> 85 | won | 7 / 7 | 3 | 0.3 s / 2.0 s |  |
| 24 | A0 r1 | 13 | hallway | Looter | 85 -> 83 (85 after) | won | 6 / 6 | 3 | 0.3 s / 0.3 s |  |
| 24 | A0 r1 | 14 | hallway | GremlinFat + GremlinWizard + GremlinThief + GremlinThief | 85 -> 84 (85 after) | won | 4 / 4 | 3 | 4.5 s / 13.6 s |  |
| 24 | A0 r1 | 16 | boss | SlimeBoss | 85 -> 53 (59 after) | won | 27 / 27 | 15 | 17.6 s / 33.4 s |  |
| 25 | A0 r1 | 1 | hallway | AcidSlime_S + SpikeSlime_M | 80 -> 80 | won | 6 / 6 | 3 | 0.0 s / 0.1 s |  |
| 25 | A0 r1 | 2 | hallway | JawWorm | 80 -> 72 (78 after) | won | 8 / 8 | 3 | 0.1 s / 0.3 s |  |
| 25 | A0 r1 | 3 | hallway | FuzzyLouseNormal + FuzzyLouseDefensive | 78 -> 78 (80 after) | won | 6 / 6 | 2 | 2.2 s / 4.0 s |  |
| 25 | A0 r1 | 4 | hallway | Looter | 80 -> 73 (79 after) | won | 14 / 14 | 5 | 0.1 s / 0.2 s |  |
| 25 | A0 r1 | 5 | hallway | JawWorm + FuzzyLouseNormal | 79 -> 76 (80 after) | won | 9 / 9 | 6 | 1.9 s / 20.8 s |  |
| 25 | A0 r1 | 7 | hallway | FungiBeast + FungiBeast | 80 -> 76 (80 after) | won | 7 / 7 | 4 | 1.4 s / 5.8 s |  |
| 25 | A0 r1 | 8 | hallway | Looter | 80 -> 75 (80 after) | won | 7 / 7 | 3 | 0.7 s / 2.8 s |  |
| 25 | A0 r1 | 12 | hallway | SpikeSlime_S + SpikeSlime_S + SpikeSlime_S + AcidSlime_S + AcidSlime_S | 74 -> 69 (74 after) | won | 14 / 14 | 10 | 12.8 s / 29.8 s |  |
| 25 | A0 r1 | 13 | hallway | SlaverRed | 74 -> 65 (71 after) | won | 8 / 8 | 9 | 20.5 s / 77.9 s |  |
| 25 | A0 r1 | 14 | elite | Lagavulin | 71 -> 53 (59 after) | won | 11 / 11 | 5 | 1.9 s / 13.8 s |  |
| 25 | A0 r1 | 16 | boss | TheGuardian | 59 -> 46 (49 after) | won | 19 / 19 | 16 | 3.8 s / 23.2 s |  |
| 26 | A0 r1 | 1 | hallway | JawWorm | 80 -> 74 (80 after) | won | 9 / 9 | 4 | 0.0 s / 0.1 s |  |
| 26 | A0 r1 | 2 | hallway | Cultist | 80 -> 74 (80 after) | won | 7 / 7 | 3 | 0.0 s / 0.1 s |  |
| 26 | A0 r1 | 3 | hallway | AcidSlime_S + SpikeSlime_M | 80 -> 80 | won | 4 / 4 | 2 | 0.1 s / 0.1 s |  |
| 26 | A0 r1 | 4 | hallway | SlaverBlue | 80 -> 69 (75 after) | won | 13 / 13 | 5 | 0.2 s / 0.3 s |  |
| 26 | A0 r1 | 5 | hallway | FungiBeast + FuzzyLouseNormal | 75 -> 66 (72 after) | won | 12 / 12 | 6 | 0.2 s / 3.4 s |  |
| 26 | A0 r1 | 6 | elite | Sentry + Sentry + Sentry | 72 -> 19 (25 after) | won | 27 / 27 | 17 | 0.3 s / 19.2 s |  |
| 26 | A0 r1 | 7 | hallway | GremlinThief + GremlinThief + GremlinWarrior + GremlinWizard | 25 -> 0 | **lost** | 7 / 7 | 7 | 1.7 s / 4.2 s |  |
| 27 | A0 r1 | 1 | hallway | JawWorm | 88 -> 82 (88 after) | won | 10 / 10 | 4 | 0.0 s / 0.0 s |  |
| 27 | A0 r1 | 3 | hallway | AcidSlime_S + SpikeSlime_M | 88 -> 86 (88 after) | won | 11 / 11 | 5 | 0.2 s / 3.1 s |  |
| 27 | A0 r1 | 4 | hallway | FuzzyLouseNormal + FuzzyLouseNormal | 88 -> 83 (88 after) | won | 4 / 4 | 3 | 0.1 s / 3.7 s |  |
| 27 | A0 r1 | 5 | hallway | SlaverBlue | 88 -> 84 (88 after) | won | 9 / 9 | 5 | 11.4 s / 12.8 s |  |
| 27 | A0 r1 | 6 | elite | Lagavulin | 88 -> 62 (68 after) | won | 20 / 20 | 7 | 0.1 s / 0.2 s |  |
| 27 | A0 r1 | 7 | hallway | AcidSlime_L | 68 -> 66 (72 after) | won | 9 / 9 | 4 | 2.4 s / 3.8 s |  |
| 27 | A0 r1 | 8 | hallway | FungiBeast + FungiBeast | 72 -> 70 (76 after) | won | 9 / 9 | 3 | 0.6 s / 3.4 s |  |
| 27 | A0 r1 | 11 | hallway | SlaverRed | 76 -> 76 (82 after) | won | 3 / 3 | 2 | 0.1 s / 0.2 s |  |
| 27 | A0 r1 | 14 | hallway | SpikeSlime_M + SlaverBlue | 82 -> 75 (81 after) | won | 8 / 8 | 4 | 1.0 s / 12.7 s |  |
| 27 | A0 r1 | 16 | boss | SlimeBoss | 81 -> 82 (88 after) | won | 30 / 31 | 10 | 0.6 s / 15.4 s |  |
| 28 | A20 r1 | 1 | hallway | FuzzyLouseNormal + FuzzyLouseDefensive | 75 -> 73 (79 after) | won | 11 / 11 | 4 | 0.1 s / 0.4 s |  |
| 28 | A20 r1 | 4 | hallway | AcidSlime_S + SpikeSlime_M | 84 -> 77 (83 after) | won | 11 / 11 | 4 | 0.1 s / 0.3 s |  |
| 28 | A20 r1 | 5 | hallway | JawWorm | 83 -> 81 (87 after) | won | 7 / 7 | 2 | 0.8 s / 1.3 s |  |
| 28 | A20 r1 | 6 | elite | GremlinNob | 87 -> 43 (49 after) | won | 12 / 12 | 5 | 0.3 s / 0.4 s |  |
| 28 | A20 r1 | 10 | hallway | FungiBeast + AcidSlime_M | 87 -> 69 (75 after) | won | 7 / 8 | 5 | 0.5 s / 10.2 s |  |
| 28 | A20 r1 | 11 | hallway | Looter | 75 -> 68 (74 after) | won | 13 / 13 | 4 | 0.0 s / 0.4 s |  |
| 28 | A20 r1 | 12 | hallway | SpikeSlime_L | 74 -> 49 (55 after) | won | 15 / 16 | 9 | 0.2 s / 0.9 s |  |
| 28 | A20 r1 | 13 | hallway | SlaverBlue | 55 -> 47 (53 after) | won | 6 / 6 | 3 | 2.3 s / 2.8 s |  |
| 28 | A20 r1 | 14 | hallway | Looter | 53 -> 53 (59 after) | won | 6 / 6 | 2 | 6.6 s / 8.4 s |  |
| 28 | A20 r1 | 16 | boss | TheGuardian | 87 -> 16 (18 after) | won | 39 / 40 | 19 | 0.7 s / 6.5 s |  |
| 29 | A20 r1 | 1 | hallway | JawWorm | 75 -> 71 (77 after) | won | 13 / 13 | 5 | 0.1 s / 0.2 s |  |
| 29 | A20 r1 | 4 | hallway | FuzzyLouseDefensive + FuzzyLouseDefensive | 77 -> 72 (78 after) | won | 14 / 14 | 5 | 0.7 s / 1.6 s |  |
| 29 | A20 r1 | 5 | hallway | Cultist | 78 -> 75 (81 after) | won | 10 / 10 | 4 | 0.3 s / 1.9 s |  |
| 29 | A20 r1 | 7 | hallway | FungiBeast + FungiBeast | 81 -> 76 (82 after) | won | 7 / 7 | 5 | 0.2 s / 2.9 s |  |
| 29 | A20 r1 | 8 | elite | GremlinNob | 82 -> 51 (44 after) | won | 13 / 13 | 4 | 0.4 s / 1.2 s |  |
| 29 | A20 r1 | 11 | hallway | Looter | 68 -> 76 (82 after) | won | 6 / 6 | 3 | 0.4 s / 3.5 s |  |
| 29 | A20 r1 | 13 | hallway | JawWorm + SpikeSlime_M | 74 -> 70 (74 after) | won | 15 / 15 | 8 | 13.4 s / 46.0 s |  |
| 29 | A20 r1 | 14 | hallway | GremlinThief + GremlinFat + GremlinWarrior + GremlinFat | 74 -> 65 (71 after) | won | 16 / 16 | 6 | 0.7 s / 27.5 s |  |
| 29 | A20 r1 | 16 | boss | Hexaghost | 71 -> 14 (20 after) | won | 24 / 24 | 13 | 1.1 s / 3.6 s |  |
| 30 | A20 r1 | 1 | hallway | AcidSlime_S + SpikeSlime_M | 75 -> 68 (74 after) | won | 8 / 8 | 3 | 0.1 s / 0.1 s |  |
| 30 | A20 r1 | 3 | hallway | JawWorm | 74 -> 65 (71 after) | won | 11 / 11 | 4 | 0.1 s / 0.2 s |  |
| 30 | A20 r1 | 4 | hallway | Cultist | 71 -> 71 (77 after) | won | 4 / 4 | 2 | 0.1 s / 0.1 s |  |
| 30 | A20 r1 | 5 | hallway | Looter | 77 -> 65 (71 after) | won | 4 / 4 | 4 | 10.2 s / 14.3 s | card Secret Technique not loaded |
| 30 | A20 r1 | 6 | hallway | AcidSlime_L | 71 -> 38 (44 after) | won | 22 / 22 | 10 | 0.2 s / 2.8 s |  |
| 30 | A20 r1 | 7 | elite | Lagavulin | 44 -> 0 | **lost** | 28 / 28 | 10 | 0.0 s / 0.1 s |  |
| 31 | A20 r1 | 1 | hallway | JawWorm | 75 -> 64 (70 after) | won | 9 / 9 | 4 | 0.1 s / 0.2 s |  |
| 31 | A20 r1 | 3 | hallway | SpikeSlime_S + AcidSlime_M | 70 -> 60 (66 after) | won | 12 / 12 | 4 | 0.2 s / 0.7 s |  |
| 31 | A20 r1 | 4 | hallway | FuzzyLouseNormal + FuzzyLouseDefensive | 66 -> 66 (72 after) | won | 4 / 4 | 1 | 1.8 s / 1.8 s |  |
| 31 | A20 r1 | 5 | hallway | SpikeSlime_L | 72 -> 72 (78 after) | won | 14 / 14 | 4 | 0.3 s / 0.6 s |  |
| 31 | A20 r1 | 7 | hallway | SpikeSlime_M + Cultist | 78 -> 74 (80 after) | won | 19 / 19 | 5 | 0.1 s / 2.3 s |  |
| 31 | A20 r1 | 11 | hallway | FuzzyLouseDefensive + FuzzyLouseNormal + FuzzyLouseNormal | 80 -> 65 (71 after) | won | 16 / 16 | 5 | 1.0 s / 4.4 s |  |
| 31 | A20 r1 | 12 | hallway | FungiBeast + AcidSlime_M | 71 -> 71 (77 after) | won | 7 / 7 | 2 | 1.1 s / 2.2 s |  |
| 31 | A20 r1 | 13 | hallway | FungiBeast + FungiBeast | 77 -> 61 (67 after) | won | 7 / 7 | 3 | 0.1 s / 1.3 s |  |
| 31 | A20 r1 | 14 | hallway | SpikeSlime_L | 67 -> 67 (73 after) | won | 13 / 13 | 5 | 2.7 s / 13.6 s |  |
| 31 | A20 r1 | 16 | boss | Hexaghost | 73 -> 31 (37 after) | won | 31 / 31 | 9 | 0.5 s / 1.7 s |  |
| 32 | A20 r1 | 1 | hallway | AcidSlime_S + SpikeSlime_M | 75 -> 71 (77 after) | won | 9 / 9 | 4 | 0.0 s / 0.1 s |  |
| 32 | A20 r1 | 4 | hallway | JawWorm | 77 -> 63 (69 after) | won | 9 / 9 | 4 | 0.0 s / 0.0 s |  |
| 32 | A20 r1 | 5 | hallway | FuzzyLouseDefensive + FuzzyLouseNormal | 69 -> 63 (69 after) | won | 3 / 3 | 2 | 0.1 s / 0.2 s |  |
| 32 | A20 r1 | 6 | elite | Sentry + Sentry + Sentry | 69 -> 24 (30 after) | won | 27 / 27 | 13 | 0.1 s / 19.2 s |  |
| 32 | A20 r1 | 10 | hallway | AcidSlime_L | 54 -> 34 (40 after) | won | 23 / 23 | 11 | 0.4 s / 2.6 s |  |
| 32 | A20 r1 | 14 | hallway | Looter | 64 -> 58 (64 after) | won | 4 / 4 | 2 | 0.5 s / 0.8 s |  |
| 32 | A20 r1 | 16 | boss | SlimeBoss | 64 -> 0 | **lost** | 21 / 21 | 10 | 0.1 s / 1.3 s |  |
| 33 | A20 r1 | 1 | hallway | SpikeSlime_S + AcidSlime_M | 68 -> 56 (62 after) | won | 13 / 13 | 5 | 0.2 s / 0.4 s |  |
| 33 | A20 r1 | 2 | hallway | JawWorm | 62 -> 60 (66 after) | won | 7 / 7 | 4 | 0.2 s / 1.8 s |  |
| 33 | A20 r1 | 3 | hallway | Cultist | 66 -> 60 (66 after) | won | 5 / 5 | 3 | 0.0 s / 0.1 s |  |
| 33 | A20 r1 | 4 | hallway | AcidSlime_M + Cultist | 66 -> 44 (50 after) | won | 9 / 9 | 7 | 0.4 s / 3.1 s |  |
| 33 | A20 r1 | 8 | elite | Sentry + Sentry + Sentry | 50 -> 8 (14 after) | won | 24 / 24 | 14 | 0.0 s / 7.2 s |  |
| 33 | A20 r1 | 10 | hallway | JawWorm + FuzzyLouseNormal | 14 -> 6 (12 after) | won | 12 / 12 | 9 | 0.2 s / 8.5 s |  |
| 33 | A20 r1 | 11 | hallway | SlaverBlue | 12 -> 4 (10 after) | won | 8 / 8 | 5 | 0.0 s / 0.8 s |  |
| 33 | A20 r1 | 12 | hallway | SpikeSlime_L | 10 -> 0 | **lost** | 5 / 5 | 3 | 0.0 s / 0.1 s |  |
| 34 | A20 r1 | 1 | hallway | FuzzyLouseNormal + FuzzyLouseNormal | 75 -> 68 (74 after) | won | 5 / 5 | 3 | 0.1 s / 0.1 s |  |
| 34 | A20 r1 | 2 | hallway | SpikeSlime_S + AcidSlime_M | 74 -> 71 (77 after) | won | 7 / 7 | 3 | 0.4 s / 0.4 s |  |
| 34 | A20 r1 | 3 | hallway | JawWorm | 77 -> 70 (76 after) | won | 10 / 10 | 3 | 0.1 s / 0.6 s |  |
| 34 | A20 r1 | 5 | hallway | SpikeSlime_L | 76 -> 58 (64 after) | won | 16 / 16 | 5 | 0.2 s / 0.6 s |  |
| 34 | A20 r1 | 7 | elite | Sentry + Sentry + Sentry | 64 -> 39 (45 after) | won | 12 / 12 | 7 | 0.2 s / 18.2 s |  |
| 34 | A20 r1 | 11 | hallway | JawWorm + AcidSlime_M | 45 -> 32 (38 after) | won | 18 / 18 | 8 | 3.2 s / 21.1 s |  |
| 34 | A20 r1 | 12 | hallway | Looter | 38 -> 27 (36 after) | won | 9 / 9 | 3 | 0.2 s / 0.3 s |  |
| 34 | A20 r1 | 13 | hallway | FungiBeast + FungiBeast + FungiBeast | 36 -> 3 (9 after) | won | 7 / 7 | 4 | 3.6 s / 12.4 s |  |
| 34 | A20 r1 | 14 | hallway | SlaverRed | 9 -> 4 (10 after) | won | 7 / 7 | 4 | 0.6 s / 13.8 s |  |
| 34 | A20 r1 | 16 | boss | SlimeBoss | 49 -> 0 | **lost** | 24 / 24 | 12 | 1.9 s / 27.7 s |  |
| 35 | A20 r2 | 1 | hallway | FuzzyLouseNormal + FuzzyLouseNormal | 68 -> 64 (70 after) | won | 6 / 6 | 3 | 0.1 s / 0.1 s |  |
| 35 | A20 r2 | 2 | hallway | JawWorm | 70 -> 63 (69 after) | won | 9 / 9 | 4 | 0.1 s / 0.1 s |  |
| 35 | A20 r2 | 4 | hallway | Cultist | 69 -> 65 (71 after) | won | 6 / 6 | 3 | 0.1 s / 0.1 s |  |
| 35 | A20 r2 | 6 | elite | GremlinNob | 71 -> 29 (35 after) | won | 12 / 12 | 5 | 0.3 s / 0.4 s |  |
| 35 | A20 r2 | 7 | hallway | Looter | 42 -> 39 (45 after) | won | 12 / 12 | 4 | 0.1 s / 0.2 s |  |
| 35 | A20 r2 | 8 | hallway | FungiBeast + FungiBeast | 45 -> 35 (41 after) | won | 13 / 13 | 5 | 0.1 s / 0.6 s |  |
| 35 | A20 r2 | 11 | hallway | GremlinWizard + GremlinTsundere + GremlinFat + GremlinThief | 41 -> 29 (35 after) | won | 15 / 15 | 5 | 0.1 s / 13.7 s |  |
| 35 | A20 r2 | 12 | hallway | FungiBeast + AcidSlime_M | 35 -> 34 (40 after) | won | 5 / 5 | 3 | 3.0 s / 27.8 s |  |
| 35 | A20 r2 | 13 | hallway | FuzzyLouseNormal + FuzzyLouseDefensive + FuzzyLouseNormal | 40 -> 34 (40 after) | won | 9 / 9 | 4 | 11.7 s / 25.4 s |  |
| 35 | A20 r2 | 14 | hallway | GremlinWizard + GremlinTsundere + GremlinWarrior + GremlinThief | 40 -> 40 (46 after) | won | 16 / 16 | 5 | 1.0 s / 11.1 s |  |
| 35 | A20 r2 | 16 | boss | Hexaghost | 70 -> 0 | **lost** | 35 / 35 | 11 | 0.1 s / 1.3 s |  |
| 36 | A20 r2 | 1 | hallway | Cultist | 68 -> 62 (68 after) | won | 10 / 10 | 4 | 0.0 s / 0.0 s |  |
| 36 | A20 r2 | 2 | hallway | FuzzyLouseNormal + FuzzyLouseNormal | 68 -> 61 (67 after) | won | 4 / 4 | 4 | 0.0 s / 0.3 s |  |
| 36 | A20 r2 | 3 | hallway | SpikeSlime_S + AcidSlime_M | 67 -> 59 (65 after) | won | 14 / 14 | 10 | 0.2 s / 2.6 s |  |
| 36 | A20 r2 | 4 | hallway | Looter | 65 -> 64 (70 after) | won | 10 / 10 | 6 | 0.2 s / 9.1 s |  |
| 36 | A20 r2 | 5 | hallway | AcidSlime_L | 70 -> 41 (47 after) | won | 36 / 36 | 21 | 0.6 s / 6.0 s |  |
| 36 | A20 r2 | 7 | hallway | AcidSlime_M + SlaverBlue | 47 -> 30 (36 after) | won | 24 / 24 | 11 | 0.3 s / 7.3 s |  |
| 36 | A20 r2 | 10 | hallway | SlaverRed | 58 -> 58 (64 after) | won | 5 / 5 | 2 | 0.4 s / 0.7 s |  |
| 36 | A20 r2 | 11 | elite | Sentry + Sentry + Sentry | 64 -> 24 (30 after) | won | 24 / 24 | 11 | 1.0 s / 20.9 s |  |
| 36 | A20 r2 | 12 | hallway | FuzzyLouseNormal + FuzzyLouseDefensive + FuzzyLouseNormal | 30 -> 30 (36 after) | won | 10 / 10 | 4 | 2.6 s / 7.8 s |  |
| 36 | A20 r2 | 14 | hallway | SlaverBlue | 58 -> 58 (64 after) | won | 12 / 12 | 7 | 0.7 s / 24.4 s |  |
| 36 | A20 r2 | 16 | boss | SlimeBoss | 64 -> 0 | **lost** | 27 / 27 | 13 | 2.6 s / 42.8 s |  |
| 37 | A20 r2 | 1 | hallway | SpikeSlime_S + AcidSlime_M | 68 -> 50 (56 after) | won | 14 / 14 | 5 | 0.1 s / 0.2 s |  |
| 37 | A20 r2 | 2 | hallway | Cultist | 56 -> 55 (61 after) | won | 7 / 7 | 3 | 0.0 s / 0.0 s |  |
| 37 | A20 r2 | 4 | hallway | JawWorm | 61 -> 52 (58 after) | won | 7 / 7 | 3 | 0.1 s / 0.2 s |  |
| 37 | A20 r2 | 5 | hallway | FungiBeast + SpikeSlime_M | 58 -> 51 (57 after) | won | 12 / 12 | 6 | 4.1 s / 12.3 s |  |
| 37 | A20 r2 | 6 | elite | GremlinNob | 57 -> 6 (12 after) | won | 11 / 11 | 5 | 0.1 s / 0.1 s |  |
| 37 | A20 r2 | 7 | hallway | FungiBeast + FungiBeast | 14 -> 14 (20 after) | won | 7 / 7 | 2 | 1.2 s / 2.1 s |  |
| 37 | A20 r2 | 8 | elite | Lagavulin | 22 -> 0 | **lost** | 18 / 18 | 9 | 7.4 s / 11.9 s |  |
| 38 | A20 r2 | 1 | hallway | FuzzyLouseNormal + FuzzyLouseNormal | 75 -> 64 (70 after) | won | 7 / 7 | 3 | 0.1 s / 0.2 s |  |
| 38 | A20 r2 | 2 | hallway | Cultist | 70 -> 69 (75 after) | won | 6 / 6 | 4 | 0.5 s / 3.3 s |  |
| 38 | A20 r2 | 3 | hallway | SpikeSlime_S + AcidSlime_M | 75 -> 73 (79 after) | won | 11 / 11 | 4 | 0.2 s / 2.3 s |  |
| 38 | A20 r2 | 4 | hallway | SpikeSlime_M + SlaverRed | 79 -> 23 (29 after) | won | 20 / 20 | 10 | 0.2 s / 12.2 s |  |
| 38 | A20 r2 | 5 | hallway | SlaverBlue | 29 -> 13 (19 after) | won | 6 / 7 | 4 | 0.3 s / 1.8 s |  |
| 38 | A20 r2 | 8 | hallway | FuzzyLouseNormal + FuzzyLouseDefensive + FuzzyLouseNormal | 43 -> 33 (39 after) | won | 9 / 9 | 5 | 1.0 s / 19.6 s |  |
| 38 | A20 r2 | 10 | hallway | Looter | 39 -> 33 (39 after) | won | 6 / 6 | 2 | 0.9 s / 1.6 s |  |
| 38 | A20 r2 | 11 | hallway | SlaverBlue | 39 -> 31 (37 after) | won | 6 / 6 | 2 | 1.4 s / 2.6 s |  |
| 38 | A20 r2 | 13 | elite | GremlinNob | 61 -> 30 (36 after) | won | 10 / 10 | 5 | 0.5 s / 2.7 s |  |
| 38 | A20 r2 | 14 | hallway | FungiBeast + FungiBeast | 36 -> 31 (37 after) | won | 10 / 10 | 6 | 2.8 s / 28.2 s |  |
| 38 | A20 r2 | 16 | boss | TheGuardian | 61 -> 0 | **lost** | 37 / 37 | 12 | 3.1 s / 28.4 s |  |
| 39 | A20 r2 | 1 | hallway | JawWorm | 68 -> 51 (57 after) | won | 12 / 12 | 5 | 0.1 s / 0.1 s |  |
| 39 | A20 r2 | 2 | hallway | Cultist | 57 -> 57 (63 after) | won | 6 / 6 | 3 | 0.0 s / 0.1 s |  |
| 39 | A20 r2 | 4 | hallway | SpikeSlime_S + AcidSlime_M | 63 -> 57 (63 after) | won | 5 / 5 | 2 | 1.3 s / 2.5 s |  |
| 39 | A20 r2 | 5 | hallway | Looter | 63 -> 57 (69 after) | won | 4 / 4 | 2 | 0.1 s / 0.2 s |  |
| 39 | A20 r2 | 6 | elite | Sentry + Sentry + Sentry | 69 -> 55 (61 after) | won | 14 / 14 | 6 | 1.5 s / 19.0 s |  |
| 39 | A20 r2 | 7 | hallway | SlaverBlue | 61 -> 61 (54 after) | won | 6 / 6 | 3 | 0.1 s / 0.1 s |  |
| 39 | A20 r2 | 8 | hallway | FungiBeast + FungiBeast | 54 -> 38 (44 after) | won | 8 / 8 | 3 | 0.1 s / 0.9 s |  |
| 39 | A20 r2 | 10 | hallway | FuzzyLouseNormal + FuzzyLouseDefensive + FuzzyLouseNormal | 44 -> 40 (46 after) | won | 8 / 8 | 5 | 0.4 s / 24.0 s |  |
| 39 | A20 r2 | 12 | hallway | FuzzyLouseNormal + Cultist | 46 -> 48 (54 after) | won | 7 / 7 | 4 | 0.3 s / 0.8 s |  |
| 39 | A20 r2 | 13 | hallway | SpikeSlime_L | 54 -> 50 (56 after) | won | 10 / 10 | 5 | 0.5 s / 0.8 s |  |
| 39 | A20 r2 | 14 | hallway | Looter | 56 -> 40 (46 after) | won | 14 / 14 | 9 | 0.3 s / 32.6 s |  |
| 39 | A20 r2 | 16 | boss | SlimeBoss | 68 -> 34 (40 after) | won | 12 / 12 | 16 | 11.2 s / 24.9 s |  |
| 40 | A20 r2 | 1 | hallway | JawWorm | 75 -> 61 (67 after) | won | 10 / 10 | 4 | 0.0 s / 0.1 s |  |
| 40 | A20 r2 | 2 | hallway | AcidSlime_S + SpikeSlime_M | 67 -> 52 (58 after) | won | 12 / 12 | 5 | 0.0 s / 0.1 s |  |
| 40 | A20 r2 | 3 | hallway | Cultist | 58 -> 57 (63 after) | won | 6 / 6 | 3 | 0.0 s / 0.0 s |  |
| 40 | A20 r2 | 4 | hallway | Looter | 63 -> 61 (67 after) | won | 11 / 11 | 5 | 0.1 s / 0.2 s |  |
| 40 | A20 r2 | 5 | hallway | SpikeSlime_L | 67 -> 46 (52 after) | won | 14 / 14 | 8 | 0.1 s / 2.1 s |  |
| 40 | A20 r2 | 7 | hallway | FungiBeast + SpikeSlime_M | 52 -> 48 (54 after) | won | 11 / 11 | 4 | 0.5 s / 7.2 s |  |
| 40 | A20 r2 | 8 | hallway | GremlinWizard + GremlinWarrior + GremlinTsundere + GremlinFat | 54 -> 17 (23 after) | won | 28 / 28 | 17 | 0.7 s / 14.0 s |  |
| 40 | A20 r2 | 12 | hallway | FungiBeast + FungiBeast + FungiBeast | 47 -> 42 (48 after) | won | 12 / 12 | 6 | 0.2 s / 21.7 s |  |
| 40 | A20 r2 | 13 | elite | Lagavulin | 48 -> 18 (24 after) | won | 16 / 17 | 9 | 0.1 s / 0.6 s |  |
| 40 | A20 r2 | 14 | hallway | FungiBeast + FungiBeast | 24 -> 24 (30 after) | won | 9 / 9 | 3 | 0.2 s / 9.6 s |  |
| 40 | A20 r2 | 16 | boss | TheGuardian | 54 -> 8 (14 after) | won | 44 / 44 | 16 | 0.3 s / 2.0 s |  |
| 41 | A20 r2 | 1 | hallway | JawWorm | 68 -> 66 (72 after) | won | 7 / 7 | 3 | 0.1 s / 0.1 s |  |
| 41 | A20 r2 | 3 | hallway | SpikeSlime_S + AcidSlime_M | 72 -> 68 (74 after) | won | 10 / 10 | 4 | 0.1 s / 2.4 s |  |
| 41 | A20 r2 | 7 | hallway | Cultist | 74 -> 73 (75 after) | won | 9 / 9 | 4 | 0.0 s / 0.1 s |  |
| 41 | A20 r2 | 10 | hallway | SlaverRed | 75 -> 55 (61 after) | won | 14 / 14 | 5 | 0.3 s / 0.9 s |  |
| 41 | A20 r2 | 11 | hallway | FungiBeast + FuzzyLouseDefensive | 61 -> 61 (67 after) | won | 8 / 8 | 3 | 1.6 s / 5.8 s |  |
| 41 | A20 r2 | 12 | elite | Lagavulin | 67 -> 46 (52 after) | won | 23 / 23 | 10 | 0.1 s / 1.4 s |  |
| 41 | A20 r2 | 14 | hallway | FuzzyLouseDefensive + FuzzyLouseDefensive + FuzzyLouseDefensive | 52 -> 57 (63 after) | won | 13 / 13 | 5 | 0.2 s / 20.8 s |  |
| 41 | A20 r2 | 16 | boss | SlimeBoss | 85 -> 33 (39 after) | won | 40 / 40 | 15 | 1.5 s / 8.5 s |  |
| 42 | A20 r2 | 1 | hallway | SpikeSlime_S + AcidSlime_M | 68 -> 50 (56 after) | won | 10 / 10 | 4 | 0.3 s / 0.9 s |  |
| 42 | A20 r2 | 2 | hallway | Cultist | 56 -> 55 (61 after) | won | 8 / 8 | 3 | 0.1 s / 0.1 s |  |
| 42 | A20 r2 | 3 | hallway | JawWorm | 61 -> 61 (67 after) | won | 2 / 2 | 2 | 2.0 s / 3.8 s |  |
| 42 | A20 r2 | 5 | hallway | FungiBeast + FungiBeast | 67 -> 62 (68 after) | won | 10 / 10 | 4 | 0.4 s / 2.0 s |  |
| 42 | A20 r2 | 7 | hallway | SlaverRed | 68 -> 68 (74 after) | won | 8 / 8 | 5 | 0.1 s / 1.1 s |  |
| 42 | A20 r2 | 10 | elite | Sentry + Sentry + Sentry | 75 -> 50 (56 after) | won | 21 / 21 | 10 | 0.0 s / 11.5 s |  |
| 42 | A20 r2 | 11 | hallway | AcidSlime_L | 58 -> 46 (52 after) | won | 9 / 9 | 8 | 15.2 s / 24.7 s |  |
| 42 | A20 r2 | 12 | hallway | FungiBeast + FungiBeast | 54 -> 50 (56 after) | won | 11 / 11 | 5 | 0.8 s / 3.0 s |  |
| 42 | A20 r2 | 13 | hallway | FungiBeast + FuzzyLouseNormal | 58 -> 58 (64 after) | won | 14 / 14 | 6 | 0.2 s / 3.8 s |  |
| 42 | A20 r2 | 16 | boss | TheGuardian | 66 -> 37 (42 after) | won | 34 / 34 | 13 | 0.2 s / 1.8 s |  |
| 43 | A20 r2 | 1 | hallway | FuzzyLouseNormal + FuzzyLouseDefensive | 75 -> 72 (78 after) | won | 11 / 11 | 4 | 0.0 s / 0.3 s |  |
| 43 | A20 r2 | 2 | hallway | AcidSlime_S + SpikeSlime_M | 78 -> 68 (74 after) | won | 10 / 10 | 4 | 0.0 s / 0.1 s |  |
| 43 | A20 r2 | 4 | hallway | Cultist | 74 -> 74 (80 after) | won | 6 / 6 | 5 | 0.2 s / 0.5 s |  |
| 43 | A20 r2 | 5 | hallway | FungiBeast + FungiBeast | 80 -> 72 (78 after) | won | 11 / 11 | 9 | 0.1 s / 1.8 s |  |
| 43 | A20 r2 | 7 | elite | Sentry + Sentry + Sentry | 78 -> 39 (45 after) | won | 28 / 28 | 15 | 0.0 s / 11.4 s |  |
| 43 | A20 r2 | 8 | hallway | FuzzyLouseNormal + FuzzyLouseDefensive + FuzzyLouseDefensive | 45 -> 43 (49 after) | won | 7 / 7 | 6 | 6.5 s / 15.1 s |  |
| 43 | A20 r2 | 10 | hallway | SlaverBlue | 49 -> 39 (45 after) | won | 6 / 6 | 5 | 0.7 s / 1.0 s |  |
| 43 | A20 r2 | 11 | elite | GremlinNob | 45 -> 14 (20 after) | won | 8 / 8 | 5 | 0.1 s / 0.9 s |  |
| 43 | A20 r2 | 12 | hallway | FungiBeast + FungiBeast | 22 -> 18 (24 after) | won | 9 / 9 | 7 | 5.8 s / 23.6 s |  |
| 43 | A20 r2 | 16 | boss | TheGuardian | 50 -> 0 | **lost** | 30 / 30 | 14 | 0.2 s / 22.1 s |  |
| 44 | A20 r2 | 1 | hallway | JawWorm | 68 -> 56 (62 after) | won | 9 / 9 | 5 | 0.1 s / 0.3 s |  |
| 44 | A20 r2 | 3 | hallway | FuzzyLouseNormal + FuzzyLouseDefensive | 62 -> 55 (61 after) | won | 4 / 4 | 3 | 0.1 s / 0.3 s |  |
| 44 | A20 r2 | 4 | hallway | Cultist | 61 -> 61 (67 after) | won | 3 / 3 | 2 | 0.1 s / 0.1 s |  |
| 44 | A20 r2 | 5 | hallway | SlaverBlue | 67 -> 66 (68 after) | won | 6 / 6 | 5 | 14.7 s / 17.3 s |  |
| 44 | A20 r2 | 7 | elite | Lagavulin | 68 -> 12 (18 after) | won | 23 / 23 | 14 | 0.1 s / 0.5 s |  |
| 44 | A20 r2 | 8 | hallway | FuzzyLouseDefensive + FuzzyLouseDefensive + FuzzyLouseNormal | 18 -> 14 (20 after) | won | 12 / 12 | 6 | 2.8 s / 8.9 s |  |
| 44 | A20 r2 | 14 | hallway | AcidSlime_L | 40 -> 40 (46 after) | won | 2 / 2 | 3 | 20.4 s / 28.5 s |  |
| 44 | A20 r2 | 16 | boss | SlimeBoss | 66 -> 3 (9 after) | won | 25 / 25 | 24 | 10.0 s / 96.1 s |  |
| 45 | A20 r2 | 1 | hallway | JawWorm | 68 -> 54 (60 after) | won | 11 / 11 | 5 | 0.0 s / 0.1 s |  |
| 45 | A20 r2 | 2 | hallway | Cultist | 60 -> 58 (64 after) | won | 11 / 11 | 4 | 0.0 s / 0.3 s |  |
| 45 | A20 r2 | 3 | hallway | AcidSlime_S + SpikeSlime_M | 64 -> 63 (69 after) | won | 6 / 6 | 3 | 0.2 s / 0.3 s |  |
| 45 | A20 r2 | 4 | hallway | SlaverBlue | 69 -> 55 (61 after) | won | 14 / 14 | 7 | 0.2 s / 0.4 s |  |
| 45 | A20 r2 | 5 | hallway | JawWorm + FuzzyLouseDefensive | 61 -> 52 (58 after) | won | 15 / 15 | 6 | 0.5 s / 2.5 s |  |
| 45 | A20 r2 | 7 | hallway | Looter | 58 -> 50 (56 after) | won | 6 / 6 | 5 | 0.2 s / 7.2 s |  |
| 45 | A20 r2 | 10 | hallway | FungiBeast + FungiBeast | 56 -> 55 (61 after) | won | 9 / 9 | 4 | 0.6 s / 0.7 s |  |
| 45 | A20 r2 | 11 | hallway | FuzzyLouseDefensive + Cultist | 61 -> 61 (67 after) | won | 15 / 15 | 5 | 2.1 s / 5.7 s |  |
| 45 | A20 r2 | 12 | hallway | AcidSlime_S + SpikeSlime_S + SpikeSlime_S + SpikeSlime_S + AcidSlime_S | 67 -> 58 (64 after) | won | 13 / 13 | 8 | 0.4 s / 58.8 s |  |
| 45 | A20 r2 | 14 | elite | GremlinNob | 64 -> 22 (28 after) | won | 11 / 11 | 5 | 0.2 s / 0.5 s |  |
| 45 | A20 r2 | 16 | boss | Hexaghost | 50 -> 0 | **lost** | 24 / 24 | 10 | 0.0 s / 45.3 s |  |
| 46 | A20 r2 | 1 | hallway | Cultist | 68 -> 62 (68 after) | won | 11 / 11 | 4 | 0.0 s / 0.1 s |  |
| 46 | A20 r2 | 3 | hallway | SpikeSlime_S + AcidSlime_M | 68 -> 52 (58 after) | won | 14 / 14 | 5 | 0.2 s / 0.9 s |  |
| 46 | A20 r2 | 4 | hallway | JawWorm | 58 -> 43 (49 after) | won | 9 / 9 | 4 | 0.1 s / 0.1 s |  |
| 46 | A20 r2 | 5 | hallway | Looter | 49 -> 42 (48 after) | won | 10 / 10 | 7 | 0.2 s / 24.8 s |  |
| 46 | A20 r2 | 6 | elite | Lagavulin | 48 -> 22 (28 after) | won | 22 / 22 | 7 | 0.0 s / 0.1 s |  |
| 46 | A20 r2 | 7 | hallway | FungiBeast + SpikeSlime_M | 28 -> 9 (15 after) | won | 14 / 14 | 5 | 0.1 s / 0.7 s |  |
| 46 | A20 r2 | 11 | hallway | SlaverRed | 59 -> 40 (46 after) | won | 11 / 11 | 7 | 0.0 s / 18.9 s |  |
| 46 | A20 r2 | 12 | hallway | FungiBeast + FungiBeast | 46 -> 43 (49 after) | won | 10 / 10 | 4 | 2.9 s / 5.6 s |  |
| 46 | A20 r2 | 16 | boss | TheGuardian | 71 -> 32 (38 after) | won | 34 / 34 | 13 | 0.1 s / 0.2 s |  |
| 47 | A20 r2 | 1 | hallway | JawWorm | 75 -> 71 (77 after) | won | 9 / 9 | 4 | 0.1 s / 0.6 s |  |
| 47 | A20 r2 | 2 | hallway | Cultist | 77 -> 71 (77 after) | won | 7 / 7 | 3 | 0.2 s / 0.2 s |  |
| 47 | A20 r2 | 3 | hallway | AcidSlime_S + SpikeSlime_M | 77 -> 65 (71 after) | won | 5 / 5 | 4 | 0.2 s / 1.4 s |  |
| 47 | A20 r2 | 4 | hallway | FuzzyLouseDefensive + FuzzyLouseDefensive + FuzzyLouseNormal | 71 -> 47 (53 after) | won | 19 / 19 | 10 | 0.1 s / 4.8 s |  |
| 47 | A20 r2 | 6 | elite | Sentry + Sentry + Sentry | 53 -> 33 (39 after) | won | 12 / 12 | 7 | 1.3 s / 20.1 s |  |
| 47 | A20 r2 | 8 | hallway | AcidSlime_M + Looter | 63 -> 39 (45 after) | won | 12 / 12 | 7 | 0.7 s / 3.9 s |  |
| 47 | A20 r2 | 10 | hallway | Looter | 45 -> 40 (46 after) | won | 3 / 3 | 2 | 0.5 s / 0.8 s |  |
| 47 | A20 r2 | 11 | hallway | FungiBeast + FungiBeast | 46 -> 38 (44 after) | won | 10 / 10 | 7 | 0.1 s / 2.4 s |  |
| 47 | A20 r2 | 12 | hallway | SlaverBlue | 44 -> 32 (38 after) | won | 10 / 10 | 5 | 1.4 s / 3.1 s |  |
| 47 | A20 r2 | 14 | hallway | FungiBeast + FuzzyLouseDefensive | 62 -> 62 (68 after) | won | 3 / 3 | 2 | 15.8 s / 31.4 s |  |
| 47 | A20 r2 | 16 | boss | SlimeBoss | 68 -> 52 (58 after) | won | 15 / 15 | 6 | 0.5 s / 4.1 s |  |
| 48 | A20 r2 | 1 | hallway | AcidSlime_S + SpikeSlime_M | 68 -> 67 (73 after) | won | 6 / 6 | 3 | 0.1 s / 0.6 s |  |
| 48 | A20 r2 | 2 | hallway | FuzzyLouseDefensive + FuzzyLouseNormal | 73 -> 72 (75 after) | won | 5 / 5 | 2 | 0.4 s / 0.5 s |  |
| 48 | A20 r2 | 3 | hallway | JawWorm | 75 -> 66 (72 after) | won | 7 / 7 | 3 | 0.1 s / 0.2 s |  |
| 48 | A20 r2 | 4 | hallway | JawWorm + FuzzyLouseNormal | 72 -> 58 (64 after) | won | 9 / 9 | 4 | 0.3 s / 8.0 s |  |
| 48 | A20 r2 | 7 | hallway | FuzzyLouseNormal + SlaverBlue | 69 -> 45 (51 after) | won | 12 / 12 | 5 | 0.2 s / 1.1 s |  |
| 48 | A20 r2 | 11 | hallway | GremlinWarrior + GremlinThief + GremlinWizard + GremlinFat | 51 -> 23 (29 after) | won | 21 / 21 | 13 | 0.4 s / 19.2 s |  |
| 48 | A20 r2 | 12 | hallway | FungiBeast + FungiBeast | 29 -> 25 (31 after) | won | 6 / 6 | 4 | 0.7 s / 2.0 s |  |
| 48 | A20 r2 | 13 | hallway | SlaverBlue | 31 -> 22 (28 after) | won | 5 / 5 | 4 | 0.3 s / 1.5 s |  |
| 48 | A20 r2 | 14 | hallway | FungiBeast + SpikeSlime_M | 28 -> 28 (34 after) | won | 5 / 5 | 2 | 1.3 s / 1.9 s |  |
| 48 | A20 r2 | 16 | boss | Hexaghost | 67 -> 0 | **lost** | 24 / 24 | 11 | 0.4 s / 34.6 s |  |
| 49 | A20 r2 | 1 | hallway | FuzzyLouseNormal + FuzzyLouseDefensive | 68 -> 62 (68 after) | won | 9 / 9 | 4 | 0.1 s / 0.1 s |  |
| 49 | A20 r2 | 2 | hallway | JawWorm | 68 -> 56 (62 after) | won | 7 / 7 | 3 | 0.3 s / 0.5 s |  |
| 49 | A20 r2 | 7 | hallway | Cultist | 62 -> 62 (68 after) | won | 9 / 9 | 3 | 0.6 s / 9.5 s |  |
| 49 | A20 r2 | 8 | hallway | FuzzyLouseDefensive + FuzzyLouseNormal + FuzzyLouseNormal | 68 -> 61 (67 after) | won | 16 / 16 | 11 | 0.0 s / 15.3 s |  |
| 49 | A20 r2 | 10 | hallway | JawWorm + SpikeSlime_M | 67 -> 21 (27 after) | won | 20 / 20 | 21 | 19.4 s / 58.4 s |  |
| 49 | A20 r2 | 11 | hallway | GremlinWarrior + GremlinWarrior + GremlinFat + GremlinThief | 27 -> 6 (12 after) | won | 16 / 16 | 12 | 9.3 s / 25.9 s |  |
| 49 | A20 r2 | 12 | hallway | AcidSlime_L | 12 -> 0 | **lost** | 10 / 10 | 6 | 2.7 s / 22.3 s |  |
| 50 | A20 r2 | 1 | hallway | FuzzyLouseNormal + FuzzyLouseDefensive | 75 -> 69 (75 after) | won | 11 / 11 | 4 | 0.1 s / 0.4 s |  |
| 50 | A20 r2 | 3 | hallway | Cultist | 75 -> 68 (74 after) | won | 11 / 11 | 4 | 0.1 s / 0.6 s |  |
| 50 | A20 r2 | 4 | hallway | JawWorm | 74 -> 65 (71 after) | won | 10 / 10 | 4 | 0.2 s / 5.2 s |  |
| 50 | A20 r2 | 5 | hallway | SpikeSlime_L | 71 -> 61 (67 after) | won | 18 / 18 | 7 | 0.4 s / 4.8 s |  |
| 50 | A20 r2 | 6 | elite | Sentry + Sentry + Sentry | 67 -> 19 (25 after) | won | 32 / 32 | 17 | 0.0 s / 8.9 s |  |
| 50 | A20 r2 | 7 | hallway | SpikeSlime_M + Looter | 25 -> 9 (15 after) | won | 11 / 11 | 4 | 1.7 s / 4.8 s |  |
| 50 | A20 r2 | 8 | elite | Lagavulin | 15 -> 0 | **lost** | 21 / 21 | 11 | 5.3 s / 20.4 s |  |
| 51 | A20 r3 | 1 | hallway | Cultist | 75 -> 74 (80 after) | won | 6 / 6 | 3 | 0.0 s / 0.0 s |  |
| 51 | A20 r3 | 3 | hallway | SpikeSlime_S + AcidSlime_M | 80 -> 70 (76 after) | won | 10 / 10 | 4 | 0.1 s / 0.2 s |  |
| 51 | A20 r3 | 7 | hallway | JawWorm | 76 -> 66 (71 after) | won | 11 / 11 | 4 | 0.1 s / 0.2 s |  |
| 51 | A20 r3 | 10 | hallway | FuzzyLouseDefensive + FuzzyLouseDefensive + FuzzyLouseNormal | 71 -> 65 (71 after) | won | 12 / 12 | 4 | 0.4 s / 3.7 s |  |
| 51 | A20 r3 | 11 | hallway | FungiBeast + FuzzyLouseDefensive | 71 -> 68 (74 after) | won | 10 / 10 | 4 | 0.4 s / 0.7 s |  |
| 51 | A20 r3 | 12 | hallway | SlaverRed | 74 -> 66 (72 after) | won | 8 / 8 | 3 | 0.2 s / 0.8 s |  |
| 51 | A20 r3 | 13 | hallway | GremlinWarrior + GremlinTsundere + GremlinFat + GremlinWarrior | 72 -> 70 (75 after) | won | 10 / 10 | 3 | 0.3 s / 8.7 s |  |
| 51 | A20 r3 | 14 | hallway | AcidSlime_M + SlaverBlue | 75 -> 70 (76 after) | won | 18 / 18 | 5 | 0.2 s / 4.7 s |  |
| 51 | A20 r3 | 16 | boss | Hexaghost | 76 -> 18 (23 after) | won | 31 / 31 | 8 | 0.0 s / 0.6 s |  |
| 52 | A20 r3 | 1 | hallway | FuzzyLouseDefensive + FuzzyLouseNormal | 75 -> 69 (75 after) | won | 10 / 10 | 4 | 0.1 s / 0.2 s |  |
| 52 | A20 r3 | 3 | hallway | AcidSlime_S + SpikeSlime_M | 75 -> 69 (75 after) | won | 13 / 13 | 8 | 0.1 s / 0.3 s |  |
| 52 | A20 r3 | 4 | hallway | Cultist | 75 -> 73 (79 after) | won | 9 / 9 | 4 | 0.1 s / 0.1 s |  |
| 52 | A20 r3 | 5 | hallway | GremlinFat + GremlinThief + GremlinFat + GremlinWizard | 79 -> 22 (28 after) | won | 39 / 39 | 17 | 0.0 s / 12.0 s |  |
| 52 | A20 r3 | 10 | elite | GremlinNob | 52 -> 0 | **lost** | 13 / 13 | 5 | 0.4 s / 5.5 s |  |
| 53 | A20 r3 | 1 | hallway | JawWorm | 75 -> 68 (74 after) | won | 10 / 10 | 4 | 0.1 s / 0.1 s |  |
| 53 | A20 r3 | 4 | hallway | Cultist | 74 -> 73 (79 after) | won | 10 / 10 | 4 | 0.0 s / 0.1 s |  |
| 53 | A20 r3 | 5 | hallway | AcidSlime_S + SpikeSlime_M | 79 -> 75 (81 after) | won | 11 / 11 | 5 | 0.0 s / 0.2 s |  |
| 53 | A20 r3 | 6 | elite | Lagavulin | 81 -> 30 (36 after) | won | 24 / 24 | 10 | 0.0 s / 0.1 s |  |
| 53 | A20 r3 | 8 | elite | Sentry + Sentry + Sentry | 60 -> 25 (31 after) | won | 19 / 19 | 10 | 0.0 s / 1.6 s |  |
| 53 | A20 r3 | 11 | hallway | SlaverBlue | 55 -> 47 (53 after) | won | 10 / 10 | 4 | 0.1 s / 0.4 s |  |
| 53 | A20 r3 | 13 | hallway | Looter | 53 -> 52 (58 after) | won | 7 / 7 | 2 | 0.2 s / 0.2 s |  |
| 53 | A20 r3 | 14 | hallway | AcidSlime_L | 58 -> 39 (45 after) | won | 18 / 18 | 6 | 3.3 s / 14.4 s |  |
| 53 | A20 r3 | 16 | boss | Hexaghost | 69 -> 0 | **lost** | 28 / 28 | 9 | 0.1 s / 0.6 s |  |
| 54 | A20 r4 | 1 | hallway | JawWorm | 68 -> 61 (67 after) | won | 10 / 10 | 4 | 0.0 s / 0.1 s |  |
| 54 | A20 r4 | 2 | hallway | SpikeSlime_S + AcidSlime_M | 67 -> 44 (50 after) | won | 13 / 13 | 8 | 0.1 s / 0.2 s |  |
| 54 | A20 r4 | 3 | hallway | Cultist | 50 -> 49 (55 after) | won | 5 / 5 | 3 | 0.0 s / 0.1 s |  |
| 54 | A20 r4 | 7 | hallway | FungiBeast + FungiBeast | 55 -> 46 (52 after) | won | 11 / 11 | 9 | 0.1 s / 0.9 s |  |
| 54 | A20 r4 | 8 | hallway | FuzzyLouseNormal + FuzzyLouseNormal + FuzzyLouseDefensive | 52 -> 48 (54 after) | won | 11 / 11 | 8 | 1.4 s / 9.6 s |  |
| 54 | A20 r4 | 11 | hallway | SlaverRed | 54 -> 50 (56 after) | won | 8 / 8 | 8 | 0.3 s / 0.9 s |  |
| 54 | A20 r4 | 13 | hallway | SlaverBlue | 56 -> 52 (58 after) | won | 5 / 5 | 5 | 0.1 s / 0.8 s |  |
| 54 | A20 r4 | 14 | elite | GremlinNob | 58 -> 58 (64 after) | won | 7 / 7 | 9 | 3.6 s / 8.7 s |  |
| 54 | A20 r4 | 16 | boss | Hexaghost | 64 -> 0 | **lost** | 20 / 20 | 19 | 0.1 s / 2.4 s |  |
| 55 | A20 r4 | 1 | hallway | Cultist | 68 -> 62 (68 after) | won | 6 / 6 | 3 | 0.0 s / 0.1 s |  |
| 55 | A20 r4 | 3 | hallway | AcidSlime_S + SpikeSlime_M | 75 -> 75 | won | 5 / 5 | 3 | 0.0 s / 0.2 s |  |
| 55 | A20 r4 | 4 | hallway | FuzzyLouseNormal + FuzzyLouseNormal | 75 -> 69 (75 after) | won | 4 / 4 | 2 | 0.4 s / 0.5 s |  |
| 55 | A20 r4 | 5 | hallway | SlaverBlue | 75 -> 67 (73 after) | won | 7 / 7 | 4 | 0.3 s / 5.4 s |  |
| 55 | A20 r4 | 6 | elite | Sentry + Sentry + Sentry | 73 -> 0 | **lost** | 32 / 32 | 16 | 0.0 s / 8.1 s |  |
| 56 | A20 r4 | 1 | hallway | Cultist | 75 -> 74 (80 after) | won | 11 / 11 | 4 | 0.0 s / 0.0 s |  |
| 56 | A20 r4 | 2 | hallway | FuzzyLouseNormal + FuzzyLouseNormal | 80 -> 76 (82 after) | won | 10 / 10 | 4 | 0.1 s / 0.4 s |  |
| 56 | A20 r4 | 3 | hallway | JawWorm | 82 -> 80 (82 after) | won | 11 / 11 | 4 | 0.3 s / 0.3 s |  |
| 56 | A20 r4 | 4 | hallway | SpikeSlime_L | 82 -> 78 (82 after) | won | 13 / 13 | 5 | 0.6 s / 10.4 s |  |
| 56 | A20 r4 | 6 | elite | Lagavulin | 82 -> 51 (57 after) | won | 27 / 27 | 8 | 0.4 s / 2.2 s |  |
| 56 | A20 r4 | 8 | elite | GremlinNob | 67 -> 47 (53 after) | won | 13 / 13 | 4 | 0.3 s / 2.0 s |  |
| 56 | A20 r4 | 11 | elite | Lagavulin | 53 -> 36 (42 after) | won | 19 / 20 | 7 | 0.3 s / 5.2 s |  |
| 56 | A20 r4 | 13 | hallway | FungiBeast + FungiBeast | 69 -> 69 (75 after) | won | 8 / 8 | 9 | 9.0 s / 10.4 s |  |
| 56 | A20 r4 | 14 | hallway | SpikeSlime_M + SlaverBlue | 75 -> 5 (11 after) | won | 40 / 40 | 26 | 0.1 s / 15.0 s |  |
| 56 | A20 r4 | 16 | boss | SlimeBoss | 38 -> 0 | **lost** | 19 / 19 | 9 | 2.2 s / 35.8 s |  |
| 57 | A20 r5 | 1 | hallway | AcidSlime_S + SpikeSlime_M | 75 -> 70 (76 after) | won | 9 / 9 | 4 | 0.2 s / 0.4 s |  |
| 57 | A20 r5 | 2 | hallway | Cultist | 76 -> 63 (69 after) | won | 12 / 12 | 5 | 0.1 s / 0.3 s |  |
| 57 | A20 r5 | 4 | hallway | FuzzyLouseDefensive + FuzzyLouseNormal | 79 -> 79 (85 after) | won | 7 / 7 | 3 | 0.2 s / 0.7 s |  |
| 57 | A20 r5 | 5 | hallway | FungiBeast + FungiBeast | 85 -> 81 (87 after) | won | 8 / 8 | 3 | 0.1 s / 0.9 s |  |
| 57 | A20 r5 | 6 | elite | GremlinNob | 87 -> 58 (64 after) | won | 13 / 13 | 4 | 0.1 s / 0.1 s |  |
| 57 | A20 r5 | 7 | hallway | SpikeSlime_M + Looter | 64 -> 52 (58 after) | won | 15 / 15 | 4 | 0.4 s / 1.7 s |  |
| 57 | A20 r5 | 10 | hallway | FuzzyLouseNormal + FuzzyLouseNormal + FuzzyLouseNormal | 58 -> 56 (62 after) | won | 11 / 11 | 3 | 1.1 s / 9.6 s |  |
| 57 | A20 r5 | 12 | hallway | SlaverRed | 62 -> 57 (63 after) | won | 8 / 8 | 7 | 4.1 s / 17.6 s |  |
| 57 | A20 r5 | 13 | hallway | Looter | 63 -> 57 (63 after) | won | 6 / 6 | 2 | 0.1 s / 0.1 s |  |
| 57 | A20 r5 | 16 | boss | SlimeBoss | 90 -> 59 (65 after) | won | 30 / 30 | 10 | 10.9 s / 91.2 s |  |
| 58 | A20 r5 g1 | 1 | hallway | FuzzyLouseDefensive + FuzzyLouseNormal | 68 -> 60 (66 after) | won | 7 / 7 | 3 | 0.0 s / 0.0 s |  |
| 58 | A20 r5 g1 | 3 | hallway | AcidSlime_S + SpikeSlime_M | 66 -> 66 (72 after) | won | 7 / 7 | 5 | 0.0 s / 0.3 s |  |
| 58 | A20 r5 g1 | 5 | hallway | Cultist | 72 -> 70 (75 after) | won | 8 / 8 | 5 | 0.0 s / 0.0 s |  |
| 58 | A20 r5 g1 | 10 | hallway | Looter | 75 -> 73 (75 after) | won | 9 / 9 | 6 | 2.8 s / 7.5 s |  |
| 58 | A20 r5 g1 | 11 | hallway | SlaverBlue | 75 -> 64 (70 after) | won | 5 / 5 | 4 | 0.1 s / 0.2 s |  |
| 58 | A20 r5 g1 | 13 | hallway | SlaverRed | 75 -> 75 (80 after) | won | 7 / 7 | 4 | 0.0 s / 0.3 s |  |
| 58 | A20 r5 g1 | 14 | hallway | SpikeSlime_L | 80 -> 71 (77 after) | won | 13 / 13 | 6 | 0.1 s / 0.2 s |  |
| 58 | A20 r5 g1 | 16 | boss | Hexaghost | 77 -> 0 | **lost** | 20 / 20 | 10 | 0.0 s / 0.3 s |  |
| 59 | A20 r5 g1 | 1 | hallway | AcidSlime_S + SpikeSlime_M | 68 -> 61 (67 after) | won | 9 / 9 | 4 | 0.0 s / 0.1 s |  |
| 59 | A20 r5 g1 | 2 | hallway | Cultist | 67 -> 66 (72 after) | won | 7 / 7 | 3 | 0.0 s / 0.0 s |  |
| 59 | A20 r5 g1 | 3 | hallway | JawWorm | 72 -> 68 (74 after) | won | 10 / 10 | 4 | 0.1 s / 0.2 s |  |
| 59 | A20 r5 g1 | 8 | hallway | AcidSlime_L | 74 -> 64 (70 after) | won | 15 / 15 | 5 | 0.2 s / 0.5 s |  |
| 59 | A20 r5 g1 | 11 | hallway | FuzzyLouseDefensive + FuzzyLouseNormal + FuzzyLouseNormal | 70 -> 70 (75 after) | won | 13 / 13 | 6 | 0.0 s / 6.5 s |  |
| 59 | A20 r5 g1 | 13 | hallway | AcidSlime_M + Cultist | 75 -> 59 (65 after) | won | 15 / 15 | 6 | 0.2 s / 0.5 s |  |
| 59 | A20 r5 g1 | 14 | hallway | Looter | 65 -> 54 (60 after) | won | 9 / 9 | 4 | 0.0 s / 0.1 s |  |
| 59 | A20 r5 g1 | 16 | boss | SlimeBoss | 60 -> 49 (55 after) | won | 22 / 22 | 7 | 0.1 s / 1.4 s |  |
| 60 | A20 r5 g1 | 1 | hallway | FuzzyLouseDefensive + FuzzyLouseDefensive | 68 -> 62 (68 after) | won | 11 / 11 | 5 | 0.0 s / 0.2 s |  |
| 60 | A20 r5 g1 | 3 | hallway | Cultist | 68 -> 67 (73 after) | won | 12 / 12 | 4 | 0.0 s / 0.0 s |  |
| 60 | A20 r5 g1 | 4 | hallway | JawWorm | 73 -> 54 (60 after) | won | 11 / 11 | 4 | 0.1 s / 0.6 s |  |
| 60 | A20 r5 g1 | 5 | hallway | FungiBeast + FungiBeast | 60 -> 58 (64 after) | won | 8 / 8 | 3 | 0.7 s / 5.8 s |  |
| 60 | A20 r5 g1 | 6 | hallway | AcidSlime_L | 64 -> 38 (44 after) | won | 22 / 22 | 7 | 0.3 s / 0.4 s |  |
| 60 | A20 r5 g1 | 8 | hallway | SlaverRed | 66 -> 40 (46 after) | won | 17 / 17 | 9 | 0.1 s / 0.2 s |  |
| 60 | A20 r5 g1 | 10 | hallway | GremlinFat + GremlinFat + GremlinThief + GremlinThief | 48 -> 48 (54 after) | won | 2 / 2 | 1 | 3.9 s / 3.9 s |  |
| 60 | A20 r5 g1 | 11 | hallway | FungiBeast + SpikeSlime_M | 56 -> 44 (50 after) | won | 9 / 9 | 6 | 0.8 s / 5.4 s |  |
| 60 | A20 r5 g1 | 12 | hallway | SlaverBlue | 52 -> 44 (50 after) | won | 13 / 13 | 5 | 0.2 s / 0.8 s |  |
| 60 | A20 r5 g1 | 13 | hallway | SlaverRed | 52 -> 47 (53 after) | won | 14 / 14 | 5 | 0.1 s / 0.2 s |  |
| 60 | A20 r5 g1 | 14 | hallway | FuzzyLouseDefensive + FuzzyLouseNormal + FuzzyLouseDefensive | 55 -> 50 (56 after) | won | 3 / 3 | 4 | 2.8 s / 5.3 s |  |
| 60 | A20 r5 g1 | 16 | boss | SlimeBoss | 75 -> 41 (38 after) | won | 18 / 18 | 10 | 0.5 s / 5.5 s |  |
| 61 | A20 r5 g1 | 1 | hallway | Cultist | 68 -> 56 (62 after) | won | 10 / 10 | 4 | 0.0 s / 0.0 s |  |
| 61 | A20 r5 g1 | 2 | hallway | AcidSlime_S + SpikeSlime_M | 62 -> 50 (56 after) | won | 11 / 11 | 5 | 0.0 s / 0.6 s |  |
| 61 | A20 r5 g1 | 3 | hallway | JawWorm | 56 -> 49 (55 after) | won | 6 / 6 | 3 | 0.0 s / 0.0 s |  |
| 61 | A20 r5 g1 | 4 | hallway | FuzzyLouseNormal + FuzzyLouseDefensive + FuzzyLouseNormal | 55 -> 36 (42 after) | won | 8 / 8 | 5 | 0.1 s / 3.3 s |  |
| 61 | A20 r5 g1 | 7 | hallway | SpikeSlime_S + SpikeSlime_S + AcidSlime_S + SpikeSlime_S + AcidSlime_S | 64 -> 61 (67 after) | won | 14 / 14 | 9 | 0.4 s / 5.2 s |  |
| 61 | A20 r5 g1 | 11 | hallway | SlaverBlue | 67 -> 59 (65 after) | won | 9 / 9 | 5 | 0.1 s / 0.2 s |  |
| 61 | A20 r5 g1 | 13 | hallway | Looter | 65 -> 59 (65 after) | won | 5 / 5 | 2 | 0.1 s / 0.2 s |  |
| 61 | A20 r5 g1 | 14 | hallway | SpikeSlime_L | 65 -> 60 (66 after) | won | 11 / 11 | 11 | 0.1 s / 5.9 s |  |
| 61 | A20 r5 g1 | 16 | boss | Hexaghost | 66 -> 0 | **lost** | 18 / 18 | 7 | 0.1 s / 0.3 s |  |
| 62 | A20 r5 g1 | 1 | hallway | AcidSlime_S + SpikeSlime_M | 68 -> 58 (64 after) | won | 7 / 7 | 3 | 0.0 s / 0.5 s |  |
| 62 | A20 r5 g1 | 2 | hallway | JawWorm | 64 -> 59 (65 after) | won | 10 / 10 | 4 | 0.1 s / 0.2 s |  |
| 62 | A20 r5 g1 | 3 | hallway | Cultist | 65 -> 65 (71 after) | won | 6 / 6 | 5 | 0.1 s / 1.7 s |  |
| 62 | A20 r5 g1 | 4 | hallway | JawWorm + SpikeSlime_M | 71 -> 51 (57 after) | won | 15 / 15 | 9 | 0.3 s / 6.7 s |  |
| 62 | A20 r5 g1 | 6 | elite | Lagavulin | 57 -> 29 (35 after) | won | 18 / 18 | 9 | 0.2 s / 7.0 s |  |
| 62 | A20 r5 g1 | 12 | hallway | Looter | 70 -> 69 (75 after) | won | 9 / 9 | 4 | 0.1 s / 0.2 s |  |
| 62 | A20 r5 g1 | 13 | hallway | SpikeSlime_S + AcidSlime_S + SpikeSlime_S + SpikeSlime_S + AcidSlime_S | 75 -> 71 (77 after) | won | 15 / 15 | 5 | 0.3 s / 6.0 s |  |
| 62 | A20 r5 g1 | 14 | hallway | FungiBeast + FungiBeast | 77 -> 71 (77 after) | won | 10 / 10 | 5 | 0.9 s / 5.1 s |  |
| 62 | A20 r5 g1 | 16 | boss | Hexaghost | 77 -> 0 | **lost** | 26 / 26 | 10 | 0.1 s / 0.3 s |  |
| 63 | A20 r5 g1 | 1 | hallway | AcidSlime_S + SpikeSlime_M | 75 -> 65 (71 after) | won | 10 / 10 | 4 | 0.0 s / 0.3 s |  |
| 63 | A20 r5 g1 | 2 | hallway | JawWorm | 71 -> 62 (68 after) | won | 11 / 11 | 5 | 0.0 s / 0.1 s |  |
| 63 | A20 r5 g1 | 3 | hallway | FuzzyLouseNormal + FuzzyLouseDefensive | 68 -> 74 (80 after) | won | 7 / 7 | 3 | 0.3 s / 0.6 s |  |
| 63 | A20 r5 g1 | 4 | hallway | SlaverBlue | 80 -> 66 (72 after) | won | 13 / 13 | 6 | 0.0 s / 0.1 s |  |
| 63 | A20 r5 g1 | 5 | hallway | Looter | 72 -> 69 (75 after) | won | 11 / 11 | 4 | 0.1 s / 0.2 s |  |
| 63 | A20 r5 g1 | 6 | elite | Sentry + Sentry + Sentry | 75 -> 15 (21 after) | won | 26 / 26 | 15 | 0.0 s / 5.2 s |  |
| 63 | A20 r5 g1 | 8 | hallway | FuzzyLouseNormal + FuzzyLouseNormal + FuzzyLouseNormal | 45 -> 38 (44 after) | won | 11 / 11 | 6 | 1.9 s / 17.7 s |  |
| 63 | A20 r5 g1 | 10 | hallway | SpikeSlime_L | 44 -> 37 (43 after) | won | 11 / 11 | 6 | 0.1 s / 0.2 s |  |
| 63 | A20 r5 g1 | 13 | hallway | FungiBeast + FungiBeast | 67 -> 67 (73 after) | won | 10 / 10 | 5 | 0.6 s / 4.8 s |  |
| 63 | A20 r5 g1 | 14 | hallway | SlaverBlue | 73 -> 62 (68 after) | won | 14 / 14 | 9 | 0.1 s / 0.5 s |  |
| 63 | A20 r5 g1 | 16 | boss | SlimeBoss | 68 -> 39 | won | 18 / 18 | 13 | 3.1 s / 6.7 s |  |
| 64 | A20 r5 g1 | 1 | hallway | JawWorm | 68 -> 49 (55 after) | won | 14 / 14 | 6 | 0.0 s / 0.1 s |  |
| 64 | A20 r5 g1 | 3 | hallway | Cultist | 55 -> 55 (61 after) | won | 5 / 5 | 3 | 0.1 s / 0.2 s |  |
| 64 | A20 r5 g1 | 4 | hallway | SpikeSlime_S + AcidSlime_M | 61 -> 44 (50 after) | won | 8 / 8 | 4 | 0.2 s / 0.5 s |  |
| 64 | A20 r5 g1 | 5 | hallway | FuzzyLouseNormal + FuzzyLouseNormal + FuzzyLouseDefensive | 50 -> 50 (56 after) | won | - | 1 | 1.1 s / 1.1 s |  |
| 64 | A20 r5 g1 | 7 | elite | GremlinNob | 56 -> 24 (30 after) | won | 8 / 8 | 4 | 0.1 s / 0.2 s |  |
| 64 | A20 r5 g1 | 8 | hallway | SpikeSlime_S + SpikeSlime_S + SpikeSlime_S + AcidSlime_S + AcidSlime_S | 30 -> 30 (36 after) | won | - | 1 | 14.7 s / 14.7 s |  |
| 64 | A20 r5 g1 | 11 | hallway | Looter | 58 -> 55 (61 after) | won | 10 / 10 | 4 | 0.1 s / 0.5 s |  |
| 64 | A20 r5 g1 | 12 | hallway | FungiBeast + FungiBeast | 61 -> 60 (66 after) | won | 7 / 7 | 3 | 0.3 s / 1.6 s |  |
| 64 | A20 r5 g1 | 16 | boss | SlimeBoss | 66 -> 40 (46 after) | won | 22 / 22 | 13 | 15.5 s / 29.7 s |  |
| 65 | A20 r5 g1 | 1 | hallway | AcidSlime_S + SpikeSlime_M | 75 -> 68 (74 after) | won | 10 / 10 | 4 | 0.1 s / 0.3 s |  |
| 65 | A20 r5 g1 | 4 | hallway | FuzzyLouseDefensive + FuzzyLouseDefensive | 74 -> 71 (77 after) | won | 4 / 4 | 2 | 0.1 s / 0.1 s |  |
| 65 | A20 r5 g1 | 6 | hallway | JawWorm | 77 -> 66 (72 after) | won | 8 / 8 | 4 | 0.1 s / 0.1 s |  |
| 65 | A20 r5 g1 | 7 | hallway | SpikeSlime_L | 72 -> 72 (78 after) | won | 15 / 15 | 7 | 1.0 s / 6.8 s |  |
| 65 | A20 r5 g1 | 8 | hallway | JawWorm + SpikeSlime_M | 78 -> 68 (74 after) | won | 12 / 12 | 4 | 2.3 s / 4.2 s |  |
| 65 | A20 r5 g1 | 10 | hallway | GremlinThief + GremlinWarrior + GremlinTsundere + GremlinThief | 74 -> 64 (70 after) | won | 12 / 12 | 8 | 5.4 s / 7.8 s |  |
| 65 | A20 r5 g1 | 12 | hallway | SlaverBlue | 70 -> 70 (76 after) | won | 6 / 6 | 4 | 4.5 s / 5.5 s |  |
| 65 | A20 r5 g1 | 13 | elite | Lagavulin | 76 -> 76 (82 after) | won | 2 / 2 | 2 | 0.1 s / 0.2 s |  |
| 65 | A20 r5 g1 | 14 | hallway | Looter | 82 -> 71 (77 after) | won | 4 / 4 | 2 | 0.3 s / 0.4 s |  |
| 65 | A20 r5 g1 | 16 | boss | SlimeBoss | 77 -> 0 | **lost** | 27 / 27 | 11 | 0.7 s / 5.4 s |  |
| 66 | A20 r5 g1 | 1 | hallway | SpikeSlime_S + AcidSlime_M | 68 -> 63 (69 after) | won | 8 / 8 | 4 | 0.0 s / 0.1 s |  |
| 66 | A20 r5 g1 | 2 | hallway | Cultist | 69 -> 63 (69 after) | won | 8 / 8 | 3 | 0.0 s / 0.0 s |  |
| 66 | A20 r5 g1 | 3 | hallway | FuzzyLouseNormal + FuzzyLouseNormal | 69 -> 69 (75 after) | won | 8 / 8 | 6 | 0.4 s / 4.8 s |  |
| 66 | A20 r5 g1 | 4 | hallway | SlaverRed | 75 -> 65 (71 after) | won | 2 / 2 | 3 | 0.0 s / 0.3 s |  |
| 66 | A20 r5 g1 | 5 | hallway | JawWorm + AcidSlime_M | 71 -> 49 (55 after) | won | 9 / 9 | 6 | 0.2 s / 5.3 s |  |
| 66 | A20 r5 g1 | 8 | elite | Lagavulin | 55 -> 27 (33 after) | won | 13 / 13 | 9 | 0.0 s / 0.1 s |  |
| 66 | A20 r5 g1 | 11 | hallway | SlaverBlue | 55 -> 45 (51 after) | won | 10 / 10 | 6 | 0.2 s / 2.2 s |  |
| 66 | A20 r5 g1 | 12 | hallway | SpikeSlime_S + AcidSlime_S + SpikeSlime_S + AcidSlime_S + SpikeSlime_S | 51 -> 40 (46 after) | won | 10 / 10 | 7 | 2.5 s / 21.9 s |  |
| 66 | A20 r5 g1 | 13 | hallway | AcidSlime_L | 46 -> 27 (33 after) | won | 13 / 13 | 7 | 0.8 s / 5.5 s |  |
| 66 | A20 r5 g1 | 14 | hallway | FuzzyLouseDefensive + FuzzyLouseDefensive + FuzzyLouseNormal | 33 -> 30 (36 after) | won | 9 / 9 | 4 | 2.8 s / 11.7 s |  |
| 66 | A20 r5 g1 | 16 | boss | TheGuardian | 58 -> 34 (36 after) | won | 34 / 34 | 14 | 0.3 s / 0.7 s |  |
| 67 | A20 r5 g1 | 1 | hallway | JawWorm | 68 -> 49 (55 after) | won | 13 / 13 | 5 | 0.0 s / 0.0 s |  |
| 67 | A20 r5 g1 | 3 | hallway | AcidSlime_S + SpikeSlime_M | 55 -> 54 (60 after) | won | 7 / 7 | 3 | 0.0 s / 0.0 s |  |
| 67 | A20 r5 g1 | 4 | hallway | FuzzyLouseNormal + FuzzyLouseNormal | 60 -> 60 (66 after) | won | 5 / 5 | 2 | 0.2 s / 0.4 s |  |
| 67 | A20 r5 g1 | 5 | hallway | FungiBeast + AcidSlime_M | 66 -> 65 (71 after) | won | 10 / 10 | 4 | 0.6 s / 3.3 s |  |
| 67 | A20 r5 g1 | 8 | hallway | SpikeSlime_S + SpikeSlime_S + AcidSlime_S + SpikeSlime_S + AcidSlime_S | 71 -> 53 (59 after) | won | 19 / 19 | 12 | 2.0 s / 8.6 s |  |
| 67 | A20 r5 g1 | 10 | hallway | SlaverBlue | 59 -> 58 (64 after) | won | 14 / 14 | 5 | 0.1 s / 0.5 s |  |
| 67 | A20 r5 g1 | 11 | hallway | FungiBeast + FungiBeast | 64 -> 59 (65 after) | won | 6 / 6 | 6 | 4.3 s / 8.3 s |  |
| 67 | A20 r5 g1 | 12 | hallway | Looter | 65 -> 64 (70 after) | won | 5 / 5 | 4 | 0.5 s / 1.8 s |  |
| 67 | A20 r5 g1 | 14 | hallway | FuzzyLouseNormal + FuzzyLouseNormal + FuzzyLouseDefensive | 70 -> 56 (62 after) | won | 9 / 9 | 5 | 0.2 s / 5.6 s |  |
| 67 | A20 r5 g1 | 16 | boss | TheGuardian | 62 -> 30 (32 after) | won | 45 / 45 | 18 | 0.1 s / 0.7 s |  |
| 68 | A20 r5 g1 | 1 | hallway | Cultist | 68 -> 67 (73 after) | won | 6 / 6 | 3 | 0.0 s / 0.0 s |  |
| 68 | A20 r5 g1 | 2 | hallway | SpikeSlime_S + AcidSlime_M | 73 -> 70 (75 after) | won | 6 / 6 | 3 | 0.1 s / 0.5 s |  |
| 68 | A20 r5 g1 | 3 | hallway | FuzzyLouseDefensive + FuzzyLouseDefensive | 75 -> 68 (74 after) | won | 5 / 5 | 3 | 0.0 s / 0.2 s |  |
| 68 | A20 r5 g1 | 4 | hallway | FungiBeast + FungiBeast | 74 -> 63 (69 after) | won | 9 / 9 | 4 | 0.0 s / 0.6 s |  |
| 68 | A20 r5 g1 | 5 | hallway | FuzzyLouseNormal + Cultist | 69 -> 69 (75 after) | won | 5 / 5 | 2 | 0.5 s / 1.0 s |  |
| 68 | A20 r5 g1 | 7 | elite | Sentry + Sentry + Sentry | 75 -> 50 (56 after) | won | 16 / 16 | 8 | 0.2 s / 1.0 s |  |
| 68 | A20 r5 g1 | 13 | hallway | SlaverRed | 56 -> 47 (53 after) | won | 3 / 3 | 3 | 0.4 s / 3.7 s |  |
| 68 | A20 r5 g1 | 14 | hallway | GremlinFat + GremlinWarrior + GremlinTsundere + GremlinThief | 53 -> 43 (49 after) | won | 12 / 12 | 7 | 0.4 s / 22.6 s |  |
| 68 | A20 r5 g1 | 16 | boss | TheGuardian | 71 -> 22 (25 after) | won | 26 / 26 | 13 | 1.3 s / 4.7 s |  |
| 69 | A20 r5 g1 | 1 | hallway | JawWorm | 68 -> 61 (67 after) | won | 7 / 7 | 3 | 0.1 s / 0.3 s |  |
| 69 | A20 r5 g1 | 2 | hallway | AcidSlime_S + SpikeSlime_M | 67 -> 66 (72 after) | won | 10 / 10 | 4 | 0.1 s / 0.1 s |  |
| 69 | A20 r5 g1 | 3 | hallway | Cultist | 72 -> 66 (72 after) | won | 7 / 7 | 4 | 0.0 s / 0.1 s |  |
| 69 | A20 r5 g1 | 4 | hallway | FungiBeast + FungiBeast | 72 -> 72 (75 after) | won | 15 / 15 | 5 | 1.0 s / 8.6 s |  |
| 69 | A20 r5 g1 | 7 | hallway | FuzzyLouseDefensive + FuzzyLouseDefensive + FuzzyLouseNormal | 75 -> 65 (71 after) | won | 10 / 10 | 6 | 5.9 s / 64.2 s |  |
| 69 | A20 r5 g1 | 8 | elite | GremlinNob | 71 -> 32 (38 after) | won | 11 / 11 | 5 | 0.2 s / 2.6 s |  |
| 69 | A20 r5 g1 | 10 | hallway | SlaverRed | 38 -> 32 (38 after) | won | 7 / 7 | 3 | 0.2 s / 0.4 s |  |
| 69 | A20 r5 g1 | 11 | hallway | GremlinTsundere + GremlinWarrior + GremlinWizard + GremlinWarrior | 38 -> 26 (32 after) | won | 12 / 12 | 14 | 4.4 s / 13.8 s |  |
| 69 | A20 r5 g1 | 14 | hallway | AcidSlime_M + Looter | 54 -> 16 (22 after) | won | 14 / 14 | 7 | 1.8 s / 20.7 s |  |
| 69 | A20 r5 g1 | 16 | boss | TheGuardian | 44 -> 0 | **lost** | 13 / 13 | 8 | 0.2 s / 1.4 s |  |
| 70 | A20 r5 g1 | 1 | hallway | SpikeSlime_S + AcidSlime_M | 68 -> 61 (67 after) | won | 7 / 7 | 3 | 0.1 s / 0.2 s |  |
| 70 | A20 r5 g1 | 2 | hallway | Cultist | 67 -> 66 (72 after) | won | 6 / 6 | 3 | 0.0 s / 0.0 s |  |
| 70 | A20 r5 g1 | 3 | hallway | JawWorm | 72 -> 68 (74 after) | won | 2 / 3 | 7 | 18.7 s / 37.7 s | the game refused a command: Invalid command: potion. Possible commands: [play, end, key, click, wait, state] |
| 70 | A20 r5 g1 | 5 | hallway | Looter | 74 -> 68 (74 after) | won | 9 / 9 | 3 | 0.1 s / 0.1 s |  |
| 70 | A20 r5 g1 | 7 | hallway | SlaverBlue | 74 -> 70 (75 after) | won | 14 / 14 | 5 | 0.1 s / 0.2 s |  |
| 70 | A20 r5 g1 | 8 | hallway | SlaverRed | 75 -> 60 (66 after) | won | 14 / 14 | 4 | 0.1 s / 0.4 s |  |
| 70 | A20 r5 g1 | 10 | hallway | Looter | 76 -> 68 (74 after) | won | 15 / 15 | 5 | 0.1 s / 0.1 s |  |
| 70 | A20 r5 g1 | 12 | hallway | SpikeSlime_L | 74 -> 73 (79 after) | won | 19 / 19 | 6 | 2.4 s / 5.8 s |  |
| 70 | A20 r5 g1 | 16 | boss | SlimeBoss | 84 -> 44 (50 after) | won | 24 / 24 | 30 | 8.4 s / 78.8 s |  |
| 71 | A20 r5 g1 | 1 | hallway | Cultist | 68 -> 67 (73 after) | won | 8 / 8 | 3 | 0.0 s / 0.0 s |  |
| 71 | A20 r5 g1 | 2 | hallway | JawWorm | 73 -> 66 (72 after) | won | 6 / 6 | 3 | 0.0 s / 0.1 s |  |
| 71 | A20 r5 g1 | 3 | hallway | AcidSlime_S + SpikeSlime_M | 72 -> 65 (71 after) | won | 7 / 7 | 4 | 0.0 s / 0.3 s |  |
| 71 | A20 r5 g1 | 4 | hallway | SlaverBlue | 71 -> 58 (64 after) | won | 8 / 8 | 3 | 0.0 s / 0.1 s |  |
| 71 | A20 r5 g1 | 5 | hallway | Looter | 64 -> 64 (70 after) | won | 10 / 10 | 4 | 0.0 s / 0.2 s |  |
| 71 | A20 r5 g1 | 7 | hallway | FungiBeast + AcidSlime_M | 70 -> 62 (68 after) | won | 13 / 13 | 5 | 0.1 s / 1.5 s |  |
| 71 | A20 r5 g1 | 8 | hallway | AcidSlime_L | 68 -> 60 (66 after) | won | 16 / 16 | 7 | 0.1 s / 1.2 s |  |
| 71 | A20 r5 g1 | 10 | hallway | SlaverRed | 66 -> 49 (55 after) | won | 10 / 10 | 5 | 0.0 s / 0.3 s |  |
| 71 | A20 r5 g1 | 12 | hallway | FungiBeast + FungiBeast + FungiBeast | 55 -> 48 (54 after) | won | 11 / 11 | 6 | 6.1 s / 15.8 s |  |
| 71 | A20 r5 g1 | 13 | elite | Lagavulin | 54 -> 32 (38 after) | won | 24 / 24 | 8 | 0.1 s / 0.2 s |  |
| 71 | A20 r5 g1 | 16 | boss | SlimeBoss | 60 -> 33 (39 after) | won | 23 / 23 | 10 | 4.8 s / 17.1 s |  |
| 72 | A20 r5 g1 | 1 | hallway | Cultist | 68 -> 67 (73 after) | won | 6 / 6 | 3 | 0.0 s / 0.0 s |  |
| 72 | A20 r5 g1 | 2 | hallway | JawWorm | 73 -> 61 (67 after) | won | 9 / 9 | 4 | 0.0 s / 0.1 s |  |
| 72 | A20 r5 g1 | 3 | hallway | SpikeSlime_S + AcidSlime_M | 67 -> 57 (63 after) | won | 7 / 7 | 5 | 0.2 s / 0.7 s |  |
| 72 | A20 r5 g1 | 4 | hallway | SlaverRed | 63 -> 46 (52 after) | won | 12 / 12 | 6 | 0.1 s / 1.0 s |  |
| 72 | A20 r5 g1 | 5 | hallway | FuzzyLouseDefensive + FuzzyLouseDefensive + FuzzyLouseDefensive | 52 -> 39 (45 after) | won | 8 / 8 | 7 | 0.2 s / 2.8 s |  |
| 72 | A20 r5 g1 | 7 | elite | Sentry + Sentry + Sentry | 45 -> 30 (21 after) | won | 11 / 12 | 10 | 11.9 s / 15.9 s |  |
| 72 | A20 r5 g1 | 8 | hallway | FungiBeast + FungiBeast | 21 -> 12 (18 after) | won | 10 / 10 | 4 | 0.3 s / 1.9 s |  |
| 72 | A20 r5 g1 | 10 | elite | GremlinNob | 18 -> 0 | **lost** | 8 / 8 | 3 | 0.0 s / 0.3 s |  |
| 73 | A20 r5 g1 | 1 | hallway | Cultist | 75 -> 69 (75 after) | won | 11 / 11 | 4 | 0.0 s / 0.0 s |  |
| 73 | A20 r5 g1 | 2 | hallway | JawWorm | 75 -> 68 (74 after) | won | 11 / 11 | 4 | 0.0 s / 0.3 s |  |
| 73 | A20 r5 g1 | 3 | hallway | FuzzyLouseDefensive + FuzzyLouseNormal | 74 -> 74 (80 after) | won | 8 / 8 | 3 | 0.1 s / 1.6 s |  |
| 73 | A20 r5 g1 | 4 | hallway | Looter | 80 -> 78 (82 after) | won | 13 / 13 | 5 | 0.0 s / 0.0 s |  |
| 73 | A20 r5 g1 | 5 | hallway | SpikeSlime_M + Cultist | 82 -> 51 (57 after) | won | 15 / 15 | 7 | 0.2 s / 0.5 s |  |
| 73 | A20 r5 g1 | 7 | elite | GremlinNob | 57 -> 35 (41 after) | won | 11 / 11 | 4 | 0.0 s / 0.1 s |  |
| 73 | A20 r5 g1 | 10 | hallway | GremlinWizard + GremlinWarrior + GremlinWarrior + GremlinThief | 65 -> 55 (61 after) | won | 12 / 12 | 5 | 0.2 s / 12.2 s |  |
| 73 | A20 r5 g1 | 11 | hallway | SlaverBlue | 61 -> 50 (56 after) | won | 11 / 11 | 4 | 0.1 s / 0.1 s |  |
| 73 | A20 r5 g1 | 12 | hallway | AcidSlime_L | 56 -> 40 (46 after) | won | 21 / 21 | 7 | 5.9 s / 21.3 s |  |
| 73 | A20 r5 g1 | 13 | hallway | SlaverRed | 46 -> 37 (43 after) | won | 11 / 11 | 4 | 0.4 s / 3.2 s |  |
| 73 | A20 r5 g1 | 16 | boss | Hexaghost | 67 -> 24 (30 after) | won | 30 / 30 | 8 | 1.1 s / 46.1 s |  |
| 74 | A20 r5 g1 | 1 | hallway | Cultist | 75 -> 69 (75 after) | won | 6 / 6 | 3 | 0.0 s / 0.0 s |  |
| 74 | A20 r5 g1 | 3 | hallway | FuzzyLouseDefensive + FuzzyLouseNormal | 75 -> 66 (72 after) | won | 7 / 7 | 4 | 0.1 s / 0.3 s |  |
| 74 | A20 r5 g1 | 4 | hallway | AcidSlime_S + SpikeSlime_M | 72 -> 72 (78 after) | won | 6 / 6 | 2 | 0.2 s / 0.3 s |  |
| 74 | A20 r5 g1 | 5 | hallway | SlaverBlue | 78 -> 64 (70 after) | won | 18 / 18 | 6 | 0.0 s / 0.1 s |  |
| 74 | A20 r5 g1 | 6 | elite | Sentry + Sentry + Sentry | 70 -> 30 (36 after) | won | 31 / 31 | 13 | 0.1 s / 2.7 s |  |
| 74 | A20 r5 g1 | 8 | elite | GremlinNob | 60 -> 35 (41 after) | won | 11 / 11 | 4 | 0.3 s / 0.5 s |  |
| 74 | A20 r5 g1 | 11 | hallway | FuzzyLouseNormal + FuzzyLouseNormal + FuzzyLouseNormal | 65 -> 64 (70 after) | won | 13 / 13 | 8 | 5.4 s / 17.8 s |  |
| 74 | A20 r5 g1 | 12 | hallway | Looter | 70 -> 69 (75 after) | won | 13 / 13 | 7 | 2.0 s / 6.8 s |  |
| 74 | A20 r5 g1 | 14 | hallway | JawWorm + AcidSlime_M | 75 -> 28 (34 after) | won | 25 / 25 | 17 | 5.1 s / 20.0 s |  |
| 74 | A20 r5 g1 | 16 | boss | SlimeBoss | 58 -> 24 (30 after) | won | 22 / 23 | 22 | 5.4 s / 8.4 s |  |
| 75 | A20 r5 g1 | 1 | hallway | FuzzyLouseNormal + FuzzyLouseNormal | 75 -> 66 (72 after) | won | 10 / 10 | 4 | 0.0 s / 0.1 s |  |
| 75 | A20 r5 g1 | 2 | hallway | JawWorm | 72 -> 60 (66 after) | won | 7 / 7 | 4 | 0.0 s / 0.1 s |  |
| 75 | A20 r5 g1 | 3 | hallway | Cultist | 66 -> 66 (72 after) | won | 5 / 5 | 3 | 0.0 s / 0.0 s |  |
| 75 | A20 r5 g1 | 4 | hallway | FungiBeast + FungiBeast | 72 -> 63 (69 after) | won | 10 / 10 | 4 | 0.1 s / 0.2 s |  |
| 75 | A20 r5 g1 | 7 | hallway | FuzzyLouseNormal + FuzzyLouseNormal + FuzzyLouseDefensive | 69 -> 61 (67 after) | won | 11 / 11 | 4 | 0.0 s / 1.1 s |  |
| 75 | A20 r5 g1 | 10 | hallway | AcidSlime_S + SpikeSlime_S + SpikeSlime_S + SpikeSlime_S + AcidSlime_S | 67 -> 40 (46 after) | won | 18 / 18 | 9 | 0.2 s / 3.5 s |  |
| 75 | A20 r5 g1 | 11 | hallway | SlaverBlue | 46 -> 43 (49 after) | won | 7 / 7 | 4 | 0.0 s / 1.0 s |  |
| 75 | A20 r5 g1 | 13 | hallway | SpikeSlime_L | 73 -> 73 (79 after) | won | 5 / 5 | 5 | 0.2 s / 1.2 s |  |
| 75 | A20 r5 g1 | 14 | hallway | Looter | 79 -> 76 (82 after) | won | 4 / 4 | 4 | 2.5 s / 8.6 s |  |
| 75 | A20 r5 g1 | 16 | boss | TheGuardian | 82 -> 69 (71 after) | won | 14 / 14 | 11 | 0.1 s / 0.6 s |  |
| 76 | A20 r5 g1 | 1 | hallway | FuzzyLouseDefensive + FuzzyLouseDefensive | 75 -> 67 (73 after) | won | 4 / 4 | 2 | 0.1 s / 0.1 s |  |
| 76 | A20 r5 g1 | 2 | hallway | SpikeSlime_S + AcidSlime_M | 73 -> 64 (70 after) | won | 8 / 8 | 4 | 0.1 s / 0.2 s |  |
| 76 | A20 r5 g1 | 4 | hallway | JawWorm | 70 -> 68 (74 after) | won | 9 / 9 | 5 | 0.1 s / 0.1 s |  |
| 76 | A20 r5 g1 | 5 | hallway | Looter | 74 -> 71 (77 after) | won | 9 / 9 | 5 | 0.2 s / 0.7 s |  |
| 76 | A20 r5 g1 | 6 | elite | GremlinNob | 77 -> 26 (32 after) | won | 11 / 11 | 7 | 0.0 s / 0.1 s |  |
| 76 | A20 r5 g1 | 8 | elite | Lagavulin | 56 -> 0 | **lost** | 33 / 33 | 16 | 0.0 s / 0.1 s |  |
| 77 | A20 r5 g1 | 1 | hallway | SpikeSlime_S + AcidSlime_M | 75 -> 55 (61 after) | won | 16 / 16 | 6 | 0.1 s / 0.1 s |  |
| 77 | A20 r5 g1 | 2 | hallway | Cultist | 61 -> 55 (61 after) | won | 5 / 5 | 3 | 0.0 s / 0.0 s |  |
| 77 | A20 r5 g1 | 3 | hallway | JawWorm | 61 -> 49 (55 after) | won | 2 / 2 | 2 | 0.1 s / 0.2 s |  |
| 77 | A20 r5 g1 | 4 | hallway | FungiBeast + AcidSlime_M | 55 -> 47 (53 after) | won | 22 / 22 | 8 | 0.1 s / 1.3 s |  |
| 77 | A20 r5 g1 | 5 | hallway | FuzzyLouseDefensive + Cultist | 53 -> 35 (41 after) | won | 9 / 9 | 7 | 0.1 s / 0.7 s |  |
| 77 | A20 r5 g1 | 7 | hallway | FungiBeast + FungiBeast | 65 -> 56 (62 after) | won | 8 / 9 | 5 | 0.1 s / 0.8 s |  |
| 77 | A20 r5 g1 | 8 | hallway | FuzzyLouseDefensive + FuzzyLouseNormal + FuzzyLouseDefensive | 62 -> 52 (58 after) | won | 13 / 13 | 13 | 8.4 s / 12.4 s |  |
| 77 | A20 r5 g1 | 11 | hallway | SlaverRed | 58 -> 38 (56 after) | won | 10 / 10 | 5 | 1.8 s / 4.6 s |  |
| 77 | A20 r5 g1 | 12 | hallway | SlaverBlue | 56 -> 40 (58 after) | won | 8 / 8 | 5 | 1.6 s / 6.2 s |  |
| 77 | A20 r5 g1 | 13 | hallway | Looter | 58 -> 52 (58 after) | won | 7 / 7 | 5 | 6.2 s / 18.1 s |  |
| 77 | A20 r5 g1 | 14 | hallway | SlaverRed | 58 -> 39 (57 after) | won | 14 / 14 | 9 | 6.1 s / 16.9 s |  |
| 77 | A20 r5 g1 | 16 | boss | TheGuardian | 81 -> 23 (41 after) | won | 39 / 39 | 22 | 1.6 s / 12.5 s |  |
| 78 | A20 r5 g1 | 1 | hallway | FuzzyLouseDefensive + FuzzyLouseDefensive | 75 -> 72 (78 after) | won | 6 / 6 | 3 | 0.1 s / 0.1 s |  |
| 78 | A20 r5 g1 | 2 | hallway | SpikeSlime_S + AcidSlime_M | 78 -> 64 (70 after) | won | 9 / 9 | 4 | 0.0 s / 0.3 s |  |
| 78 | A20 r5 g1 | 3 | hallway | JawWorm | 70 -> 66 (72 after) | won | 6 / 6 | 3 | 0.0 s / 0.1 s |  |
| 78 | A20 r5 g1 | 5 | hallway | GremlinTsundere + GremlinThief + GremlinFat + GremlinWizard | 72 -> 38 (44 after) | won | 19 / 19 | 8 | 0.0 s / 3.0 s |  |
| 78 | A20 r5 g1 | 7 | elite | GremlinNob | 68 -> 30 (36 after) | won | 13 / 13 | 5 | 0.0 s / 0.0 s |  |
| 78 | A20 r5 g1 | 10 | hallway | SpikeSlime_L | 60 -> 49 (55 after) | won | 13 / 13 | 10 | 7.4 s / 14.6 s |  |
| 78 | A20 r5 g1 | 11 | hallway | FuzzyLouseNormal + SlaverRed | 55 -> 17 (23 after) | won | 6 / 6 | 3 | 0.4 s / 2.1 s | controller error: a creature holding 12 powers (POWER_CAP) gained a new one, Gen7 |
| 78 | A20 r5 g1 | 12 | hallway | FuzzyLouseNormal + FuzzyLouseNormal + FuzzyLouseDefensive | 23 -> 5 (11 after) | won | 7 / 7 | 6 | 0.6 s / 17.8 s |  |
| 78 | A20 r5 g1 | 13 | hallway | Looter | 11 -> 0 | **lost** | 4 / 4 | 2 | 0.7 s / 1.4 s |  |
| 79 | A20 r5 g1 | 1 | hallway | JawWorm | 75 -> 61 (67 after) | won | 10 / 10 | 4 | 0.0 s / 0.1 s |  |
| 79 | A20 r5 g1 | 2 | hallway | AcidSlime_S + SpikeSlime_M | 67 -> 57 (63 after) | won | 8 / 8 | 3 | 0.1 s / 0.8 s |  |
| 79 | A20 r5 g1 | 3 | hallway | Cultist | 63 -> 57 (63 after) | won | 8 / 8 | 4 | 0.0 s / 0.0 s |  |
| 79 | A20 r5 g1 | 5 | hallway | GremlinThief + GremlinWizard + GremlinTsundere + GremlinWarrior | 63 -> 63 (69 after) | won | 21 / 21 | 7 | 0.0 s / 3.7 s |  |
| 79 | A20 r5 g1 | 7 | hallway | SlaverBlue | 69 -> 58 (64 after) | won | 11 / 11 | 5 | 0.0 s / 0.1 s |  |
| 79 | A20 r5 g1 | 8 | elite | GremlinNob | 64 -> 56 (62 after) | won | 6 / 6 | 3 | 0.0 s / 0.1 s |  |
| 79 | A20 r5 g1 | 10 | elite | Lagavulin | 62 -> 0 | **lost** | 32 / 32 | 12 | 0.0 s / 0.1 s |  |
| 80 | A20 r5 g1 | 1 | hallway | Cultist | 75 -> 68 (74 after) | won | 11 / 11 | 4 | 0.0 s / 0.0 s |  |
| 80 | A20 r5 g1 | 2 | hallway | SpikeSlime_S + AcidSlime_M | 74 -> 62 (68 after) | won | 14 / 14 | 5 | 0.4 s / 1.1 s |  |
| 80 | A20 r5 g1 | 3 | hallway | JawWorm | 68 -> 51 (57 after) | won | 10 / 10 | 4 | 0.5 s / 1.0 s |  |
| 80 | A20 r5 g1 | 4 | hallway | AcidSlime_M + Looter | 57 -> 35 (41 after) | won | 7 / 7 | 5 | 1.3 s / 1.9 s |  |
| 80 | A20 r5 g1 | 7 | elite | GremlinNob | 65 -> 35 (41 after) | won | 11 / 11 | 7 | 0.0 s / 0.1 s |  |
| 80 | A20 r5 g1 | 8 | hallway | FungiBeast + FungiBeast | 41 -> 41 (47 after) | won | 7 / 8 | 3 | 0.8 s / 0.8 s |  |
| 80 | A20 r5 g1 | 11 | hallway | SpikeSlime_L | 47 -> 32 (38 after) | won | 13 / 13 | 7 | 0.0 s / 0.2 s |  |
| 80 | A20 r5 g1 | 13 | hallway | FuzzyLouseDefensive + FuzzyLouseNormal + FuzzyLouseDefensive | 62 -> 65 (71 after) | won | 14 / 14 | 7 | 1.8 s / 11.4 s |  |
| 80 | A20 r5 g1 | 14 | hallway | FungiBeast + FungiBeast | 71 -> 71 (77 after) | won | 9 / 9 | 7 | 2.8 s / 9.7 s |  |
| 80 | A20 r5 g1 | 16 | boss | Hexaghost | 77 -> 0 | **lost** | 30 / 30 | 13 | 0.0 s / 0.1 s |  |
| 81 | A20 r5 g1 | 1 | hallway | JawWorm | 68 -> 62 (68 after) | won | 18 / 18 | 7 | 0.0 s / 0.0 s |  |
| 81 | A20 r5 g1 | 2 | hallway | Cultist | 68 -> 62 (68 after) | won | 8 / 8 | 4 | 0.0 s / 0.1 s |  |
| 81 | A20 r5 g1 | 3 | hallway | AcidSlime_S + SpikeSlime_M | 68 -> 67 (73 after) | won | 8 / 8 | 4 | 0.1 s / 0.4 s |  |
| 81 | A20 r5 g1 | 5 | hallway | FungiBeast + AcidSlime_M | 73 -> 37 (43 after) | won | 22 / 22 | 9 | 0.1 s / 0.5 s |  |
| 81 | A20 r5 g1 | 7 | hallway | FungiBeast + FungiBeast | 65 -> 54 (60 after) | won | 11 / 11 | 7 | 0.3 s / 12.4 s |  |
| 81 | A20 r5 g1 | 8 | hallway | AcidSlime_M + Cultist | 60 -> 36 (42 after) | won | 17 / 17 | 6 | 0.1 s / 0.8 s |  |
| 81 | A20 r5 g1 | 10 | hallway | FungiBeast + AcidSlime_M | 42 -> 43 (49 after) | won | 10 / 10 | 4 | 0.4 s / 3.4 s |  |
| 81 | A20 r5 g1 | 12 | hallway | AcidSlime_L | 49 -> 44 (50 after) | won | 16 / 16 | 6 | 0.3 s / 17.1 s |  |
| 81 | A20 r5 g1 | 16 | boss | TheGuardian | 73 -> 31 (35 after) | won | 35 / 35 | 13 | 0.1 s / 0.2 s |  |
| 82 | A20 r5 g1 | 1 | hallway | SpikeSlime_S + AcidSlime_M | 68 -> 58 (64 after) | won | 9 / 9 | 4 | 0.1 s / 0.3 s |  |
| 82 | A20 r5 g1 | 2 | hallway | Cultist | 64 -> 64 (70 after) | won | 7 / 7 | 3 | 0.0 s / 0.1 s |  |
| 82 | A20 r5 g1 | 3 | hallway | FuzzyLouseNormal + FuzzyLouseDefensive | 70 -> 61 (67 after) | won | 9 / 9 | 4 | 0.2 s / 0.4 s |  |
| 82 | A20 r5 g1 | 4 | hallway | SpikeSlime_L | 67 -> 53 (59 after) | won | 16 / 16 | 7 | 0.1 s / 0.5 s |  |
| 82 | A20 r5 g1 | 6 | hallway | GremlinFat + GremlinWizard + GremlinFat + GremlinWarrior | 59 -> 37 (43 after) | won | 18 / 18 | 8 | 1.5 s / 18.3 s |  |
| 82 | A20 r5 g1 | 7 | hallway | JawWorm + AcidSlime_M | 43 -> 34 (40 after) | won | 14 / 14 | 5 | 0.1 s / 6.3 s |  |
| 82 | A20 r5 g1 | 8 | hallway | SlaverRed | 40 -> 29 (35 after) | won | 7 / 7 | 5 | 0.0 s / 4.0 s |  |
| 82 | A20 r5 g1 | 14 | hallway | Looter | 57 -> 62 (68 after) | won | 6 / 6 | 2 | 0.1 s / 0.2 s |  |
| 82 | A20 r5 g1 | 16 | boss | Hexaghost | 68 -> 0 | **lost** | 30 / 30 | 15 | 0.1 s / 5.4 s |  |
| 83 | A20 r5 g1 | 1 | hallway | Cultist | 68 -> 62 (68 after) | won | 6 / 6 | 3 | 0.0 s / 0.0 s |  |
| 83 | A20 r5 g1 | 2 | hallway | JawWorm | 68 -> 54 (60 after) | won | 18 / 18 | 7 | 0.1 s / 0.6 s |  |
| 83 | A20 r5 g1 | 3 | hallway | FuzzyLouseDefensive + FuzzyLouseDefensive | 60 -> 54 (60 after) | won | 7 / 7 | 4 | 0.7 s / 18.9 s |  |
| 83 | A20 r5 g1 | 5 | hallway | GremlinWarrior + GremlinTsundere + GremlinWarrior + GremlinThief | 60 -> 8 (14 after) | won | 202 / 202 | 87 | 0.0 s / 16.4 s |  |
| 83 | A20 r5 g1 | 7 | elite | Lagavulin | 36 -> 0 | **lost** | 17 / 17 | 12 | 0.0 s / 0.4 s |  |
| 84 | A20 r5 g1 | 1 | hallway | FuzzyLouseDefensive + FuzzyLouseNormal | 75 -> 66 (72 after) | won | 5 / 5 | 2 | 0.0 s / 0.0 s |  |
| 84 | A20 r5 g1 | 2 | hallway | Cultist | 72 -> 71 (77 after) | won | 7 / 7 | 3 | 0.0 s / 0.0 s |  |
| 84 | A20 r5 g1 | 3 | hallway | JawWorm | 77 -> 75 (81 after) | won | 8 / 8 | 3 | 0.1 s / 0.2 s |  |
| 84 | A20 r5 g1 | 7 | hallway | SlaverRed | 81 -> 72 (78 after) | won | 7 / 7 | 4 | 0.2 s / 0.9 s |  |
| 84 | A20 r5 g1 | 10 | hallway | AcidSlime_M + Cultist | 78 -> 59 (65 after) | won | 16 / 16 | 15 | 9.7 s / 16.3 s |  |
| 84 | A20 r5 g1 | 12 | hallway | SlaverBlue | 65 -> 62 (68 after) | won | 8 / 8 | 4 | 0.9 s / 8.6 s |  |
| 84 | A20 r5 g1 | 13 | hallway | GremlinWizard + GremlinThief + GremlinFat + GremlinWarrior | 68 -> 53 (59 after) | won | 13 / 13 | 12 | 3.5 s / 13.2 s |  |
| 84 | A20 r5 g1 | 14 | hallway | AcidSlime_S + SpikeSlime_S + SpikeSlime_S + AcidSlime_S + SpikeSlime_S | 59 -> 53 (59 after) | won | 15 / 15 | 15 | 6.0 s / 8.9 s |  |
| 84 | A20 r5 g1 | 16 | boss | SlimeBoss | 82 -> 58 (64 after) | won | 15 / 15 | 18 | 4.0 s / 11.4 s |  |
| 85 | A20 r5 g1 | 1 | hallway | SpikeSlime_S + AcidSlime_M | 75 -> 70 (76 after) | won | 11 / 11 | 4 | 0.0 s / 0.0 s |  |
| 85 | A20 r5 g1 | 2 | hallway | JawWorm | 76 -> 69 (75 after) | won | 6 / 6 | 3 | 0.1 s / 0.1 s |  |
| 85 | A20 r5 g1 | 4 | hallway | FuzzyLouseNormal + FuzzyLouseNormal | 75 -> 75 (81 after) | won | 3 / 3 | 2 | 0.2 s / 0.3 s |  |
| 85 | A20 r5 g1 | 5 | hallway | FungiBeast + FungiBeast | 81 -> 81 (82 after) | won | 5 / 5 | 2 | 0.4 s / 0.6 s |  |
| 85 | A20 r5 g1 | 7 | hallway | GremlinThief + GremlinThief + GremlinWarrior + GremlinWarrior | 82 -> 62 (68 after) | won | 15 / 15 | 6 | 0.1 s / 0.2 s |  |
| 85 | A20 r5 g1 | 11 | hallway | SpikeSlime_M + SlaverRed | 68 -> 60 (66 after) | won | 16 / 16 | 6 | 0.1 s / 2.6 s |  |
| 85 | A20 r5 g1 | 12 | hallway | SpikeSlime_S + SpikeSlime_S + SpikeSlime_S + AcidSlime_S + AcidSlime_S | 66 -> 50 (56 after) | won | 14 / 14 | 6 | 0.6 s / 4.5 s |  |
| 85 | A20 r5 g1 | 13 | hallway | FungiBeast + FungiBeast + FungiBeast | 56 -> 32 (38 after) | won | 13 / 13 | 6 | 0.6 s / 2.7 s |  |
| 85 | A20 r5 g1 | 14 | hallway | AcidSlime_L | 38 -> 18 (24 after) | won | 9 / 9 | 10 | 0.8 s / 16.4 s |  |
| 85 | A20 r5 g1 | 16 | boss | Hexaghost | 48 -> 0 | **lost** | 21 / 21 | 11 | 0.0 s / 6.4 s |  |
| 86 | A20 r5 g1 | 1 | hallway | FuzzyLouseNormal + FuzzyLouseNormal | 68 -> 65 (71 after) | won | 7 / 7 | 3 | 0.0 s / 0.0 s |  |
| 86 | A20 r5 g1 | 2 | hallway | Cultist | 71 -> 70 (75 after) | won | 6 / 6 | 4 | 0.0 s / 0.0 s |  |
| 86 | A20 r5 g1 | 3 | hallway | JawWorm | 75 -> 75 | won | 2 / 2 | 1 | 0.0 s / 0.0 s |  |
| 86 | A20 r5 g1 | 4 | hallway | SlaverRed | 75 -> 65 (71 after) | won | 9 / 9 | 7 | 0.0 s / 0.1 s |  |
| 86 | A20 r5 g1 | 5 | hallway | SpikeSlime_L | 71 -> 54 (60 after) | won | 17 / 17 | 8 | 0.2 s / 2.3 s |  |
| 86 | A20 r5 g1 | 7 | hallway | FungiBeast + FungiBeast | 60 -> 60 (66 after) | won | 6 / 6 | 5 | 1.3 s / 23.1 s |  |
| 86 | A20 r5 g1 | 10 | hallway | AcidSlime_M + Looter | 66 -> 45 (51 after) | won | 6 / 6 | 5 | 0.5 s / 3.3 s |  |
| 86 | A20 r5 g1 | 12 | hallway | SlaverRed | 51 -> 45 (51 after) | won | 2 / 2 | 3 | 0.2 s / 0.8 s |  |
| 86 | A20 r5 g1 | 13 | hallway | JawWorm + AcidSlime_M | 51 -> 38 (44 after) | won | 12 / 12 | 8 | 0.3 s / 16.8 s |  |
| 86 | A20 r5 g1 | 14 | hallway | SlaverBlue | 44 -> 38 (44 after) | won | 5 / 5 | 4 | 0.0 s / 1.3 s |  |
| 86 | A20 r5 g1 | 16 | boss | SlimeBoss | 66 -> 31 (37 after) | won | 21 / 21 | 11 | 0.5 s / 9.0 s |  |
| 87 | A20 r5 g1 | 1 | hallway | Cultist | 68 -> 62 (68 after) | won | 9 / 9 | 3 | 0.0 s / 0.0 s |  |
| 87 | A20 r5 g1 | 2 | hallway | AcidSlime_S + SpikeSlime_M | 68 -> 73 (75 after) | won | 6 / 6 | 2 | 0.2 s / 0.4 s |  |
| 87 | A20 r5 g1 | 3 | hallway | FuzzyLouseNormal + FuzzyLouseNormal | 75 -> 75 | won | - | 1 | 0.3 s / 0.3 s |  |
| 87 | A20 r5 g1 | 5 | hallway | JawWorm + SpikeSlime_M | 75 -> 65 (71 after) | won | 17 / 17 | 6 | 0.3 s / 7.2 s |  |
| 87 | A20 r5 g1 | 7 | hallway | FuzzyLouseDefensive + FuzzyLouseNormal + FuzzyLouseDefensive | 71 -> 60 (66 after) | won | 10 / 10 | 4 | 0.1 s / 1.4 s |  |
| 87 | A20 r5 g1 | 8 | hallway | SpikeSlime_L | 66 -> 66 (70 after) | won | 9 / 9 | 3 | 0.2 s / 1.0 s |  |
| 87 | A20 r5 g1 | 10 | hallway | SlaverBlue | 70 -> 69 (75 after) | won | 7 / 7 | 4 | 3.0 s / 8.4 s |  |
| 87 | A20 r5 g1 | 12 | hallway | FuzzyLouseNormal + FuzzyLouseNormal + FuzzyLouseNormal | 75 -> 56 (62 after) | won | 6 / 6 | 3 | 0.3 s / 3.9 s |  |
| 87 | A20 r5 g1 | 13 | hallway | Looter | 62 -> 65 (71 after) | won | 6 / 6 | 2 | 0.1 s / 0.1 s |  |
| 87 | A20 r5 g1 | 14 | hallway | SlaverRed | 71 -> 64 (70 after) | won | 3 / 3 | 2 | 0.2 s / 0.2 s |  |
| 87 | A20 r5 g1 | 16 | boss | Hexaghost | 70 -> 0 | **lost** | 27 / 27 | 9 | 0.0 s / 0.3 s |  |
| 88 | A20 r5 g1 | 1 | hallway | AcidSlime_S + SpikeSlime_M | 75 -> 71 (77 after) | won | 6 / 6 | 3 | 0.0 s / 0.2 s |  |
| 88 | A20 r5 g1 | 2 | hallway | Cultist | 77 -> 71 (77 after) | won | 6 / 6 | 3 | 0.0 s / 0.0 s |  |
| 88 | A20 r5 g1 | 3 | hallway | FuzzyLouseDefensive + FuzzyLouseDefensive | 77 -> 74 (80 after) | won | 14 / 14 | 8 | 0.0 s / 0.8 s |  |
| 88 | A20 r5 g1 | 4 | hallway | SpikeSlime_L | 80 -> 75 (81 after) | won | 14 / 14 | 7 | 0.1 s / 1.2 s |  |
| 88 | A20 r5 g1 | 6 | elite | Lagavulin | 81 -> 49 (55 after) | won | 23 / 23 | 16 | 0.1 s / 4.7 s |  |
| 88 | A20 r5 g1 | 8 | hallway | GremlinWarrior + GremlinFat + GremlinThief + GremlinWarrior | 55 -> 45 (51 after) | won | 11 / 11 | 11 | 0.3 s / 28.5 s |  |
| 88 | A20 r5 g1 | 11 | hallway | SpikeSlime_S + SpikeSlime_S + AcidSlime_S + SpikeSlime_S + AcidSlime_S | 51 -> 35 (41 after) | won | 12 / 12 | 8 | 1.7 s / 10.3 s |  |
| 88 | A20 r5 g1 | 13 | hallway | JawWorm + AcidSlime_M | 65 -> 48 (54 after) | won | 14 / 14 | 7 | 0.1 s / 12.9 s |  |
| 88 | A20 r5 g1 | 16 | boss | TheGuardian | 78 -> 55 (61 after) | won | 30 / 30 | 15 | 0.1 s / 0.4 s |  |
| 89 | A20 r5 g1 | 1 | hallway | Cultist | 75 -> 69 (75 after) | won | 7 / 7 | 3 | 0.0 s / 0.0 s |  |
| 89 | A20 r5 g1 | 2 | hallway | JawWorm | 75 -> 64 (70 after) | won | 11 / 11 | 4 | 0.0 s / 0.4 s |  |
| 89 | A20 r5 g1 | 3 | hallway | AcidSlime_S + SpikeSlime_M | 70 -> 63 (69 after) | won | 5 / 5 | 3 | 0.1 s / 0.1 s |  |
| 89 | A20 r5 g1 | 4 | hallway | Looter | 69 -> 65 (71 after) | won | 8 / 8 | 4 | 0.0 s / 0.1 s |  |
| 89 | A20 r5 g1 | 5 | hallway | SpikeSlime_L | 71 -> 71 (77 after) | won | 9 / 9 | 4 | 0.1 s / 0.2 s |  |
| 89 | A20 r5 g1 | 7 | hallway | FuzzyLouseDefensive + FuzzyLouseDefensive + FuzzyLouseNormal | 77 -> 64 (70 after) | won | 8 / 8 | 4 | 0.3 s / 4.9 s |  |
| 89 | A20 r5 g1 | 10 | hallway | SlaverBlue | 72 -> 65 (71 after) | won | 9 / 9 | 4 | 0.4 s / 0.8 s |  |
| 89 | A20 r5 g1 | 11 | hallway | FungiBeast + SpikeSlime_M | 73 -> 71 (77 after) | won | 10 / 10 | 4 | 0.3 s / 3.6 s |  |
| 89 | A20 r5 g1 | 13 | hallway | FungiBeast + FungiBeast | 79 -> 73 (79 after) | won | 10 / 10 | 5 | 0.3 s / 1.4 s |  |
| 89 | A20 r5 g1 | 14 | hallway | SlaverBlue | 81 -> 68 (74 after) | won | 6 / 6 | 3 | 1.8 s / 3.4 s |  |
| 89 | A20 r5 g1 | 16 | boss | SlimeBoss | 76 -> 44 (50 after) | won | 27 / 27 | 31 | 7.0 s / 66.8 s |  |
| 90 | A20 r5 g1 | 1 | hallway | Cultist | 75 -> 63 (69 after) | won | 9 / 9 | 4 | 0.0 s / 0.0 s |  |
| 90 | A20 r5 g1 | 2 | hallway | AcidSlime_S + SpikeSlime_M | 69 -> 61 (67 after) | won | 10 / 10 | 5 | 0.1 s / 1.6 s |  |
| 90 | A20 r5 g1 | 3 | hallway | FuzzyLouseDefensive + FuzzyLouseNormal | 67 -> 57 (63 after) | won | 9 / 9 | 4 | 0.0 s / 0.5 s |  |
| 90 | A20 r5 g1 | 4 | hallway | Looter | 63 -> 51 (57 after) | won | 7 / 7 | 3 | 0.0 s / 0.0 s |  |
| 90 | A20 r5 g1 | 7 | hallway | FuzzyLouseDefensive + FuzzyLouseDefensive + FuzzyLouseNormal | 57 -> 44 (50 after) | won | 5 / 5 | 3 | 0.2 s / 2.4 s |  |
| 90 | A20 r5 g1 | 8 | hallway | SpikeSlime_M + SlaverBlue | 50 -> 14 (20 after) | won | 17 / 17 | 9 | 0.2 s / 18.1 s |  |
| 90 | A20 r5 g1 | 14 | elite | GremlinNob | 44 -> 13 (19 after) | won | 8 / 8 | 5 | 0.1 s / 0.1 s |  |
| 90 | A20 r5 g1 | 16 | boss | Hexaghost | 43 -> 0 | **lost** | 24 / 24 | 11 | 0.0 s / 0.1 s |  |

## Fallbacks

- card Dual Wield not loaded: 1 fight(s), floors 14.
- card Rampage{damage=13/combat} not in the game's hand: 1 fight(s), floors 10.
- card Secret Technique not loaded: 1 fight(s), floors 5.
- card Strike{cost=0/combat} not in the game's hand: 1 fight(s), floors 10.
- card gen:Blood for Blood+ not in the game's hand: 1 fight(s), floors 16.
- controller error: a creature holding 12 powers (POWER_CAP) gained a new one, Gen7: 1 fight(s), floors 11.
- monster not loaded (Act 2 and later): 56 fight(s), floors 18, 20, 18, 20, 21, 22, 27, 18, 19, 20, 23, 20, 18, 19, 21, 22, 23, 18, 19, 24, 27, 30, 31, 18, 19, 20, 21, 18, 19, 20, 21, 18, 20, 21, 22, 18, 21, 18, 20, 21, 22, 18, 19, 20, 18, 19, 21, 18, 18, 20, 21, 18, 19, 20, 21, 18.
- move None of Cultist not mapped: 2 fight(s), floors 25, 21.
- move None of Looter not mapped: 1 fight(s), floors 18.
- the game refused a command: Invalid command: potion. Possible commands: [play, end, key, click, wait, state]: 1 fight(s), floors 3.
- the plan has no pick here: 2 fight(s), floors 13, 12.

## Prediction misses

- Run 1, floor 14 (SpikeSlime_M + Cultist), turn 4: monsters[0].hp.
- Run 1, floor 16 (TheGuardian), turn 6: cards_played_this_turn.
- Run 1, floor 16 (TheGuardian), turn 12: cards_played_this_turn, monsters[0].hp.
- Run 2, floor 12 (FungiBeast + AcidSlime_M), turn 3: cards_played_this_turn.
- Run 2, floor 12 (FungiBeast + AcidSlime_M), turn 6: cards_played_this_turn.
- Run 2, floor 16 (TheGuardian), turn 6: cards_played_this_turn.
- Run 8, floor 16 (TheGuardian), turn 8: monsters[0].block.
- Run 10, floor 5 (FungiBeast + FungiBeast), turn 2: discard.Strike, discard.Strike{cost=0/combat}.
- Run 12, floor 11 (Lagavulin), turn 4: player.hp, player.relics[0].value.
- Run 12, floor 11 (Lagavulin), turn 6: player.relics[0].value.
- Run 12, floor 14 (SpikeSlime_S + SpikeSlime_S + AcidSlime_S + SpikeSlime_S + AcidSlime_S), turn 3: player.relics[0].value.
- Run 12, floor 16 (SlimeBoss), turn 3: player.relics[0].value.
- Run 13, floor 16 (TheGuardian), turn 1: player.energy.
- Run 14, floor 11 (GremlinThief + GremlinTsundere + GremlinWizard + GremlinWarrior), turn 1: player.powers.Barricade.
- Run 15, floor 14 (FungiBeast + FuzzyLouseNormal), turn 2: draw.Defend, draw.gen:Armaments, hand.Defend, hand.gen:Armaments.
- Run 15, floor 16 (TheGuardian), turn 2: draw.Defend, draw.Strike, hand.Defend, hand.Strike.
- Run 16, floor 14 (FuzzyLouseNormal + FuzzyLouseNormal + FuzzyLouseDefensive), turn 1: player.hp, player.max_hp.
- Run 21, floor 16 (Hexaghost), turn 5: free.Clash+.
- Run 22, floor 7 (SlaverRed), turn 1: discard.Bash, discard.Cleave, discard.Strike, draw.Bash, draw.Cleave, draw.Strike, draw.gen:Fire Breathing, monsters[0].hp, monsters[0].powers.Vulnerable, player.powers.FireBreathing.
- Run 23, floor 7 (FungiBeast + FungiBeast), turn 1: player.powers.NoDraw.
- Run 23, floor 8 (FuzzyLouseDefensive + Looter), turn 2: player.powers.NoDraw.
- Run 23, floor 8 (FuzzyLouseDefensive + Looter), turn 4: player.powers.NoDraw.
- Run 23, floor 11 (Looter), turn 1: player.powers.NoDraw.
- Run 23, floor 12 (SlaverRed), turn 2: player.hp.
- Run 23, floor 16 (TheGuardian), turn 3: player.hp.
- Run 23, floor 16 (TheGuardian), turn 6: player.powers.NoDraw.
- Run 23, floor 16 (TheGuardian), turn 14: player.hp.
- Run 23, floor 16 (TheGuardian), turn 14: player.hp.
- Run 23, floor 16 (TheGuardian), turn 15: player.hp.
- Run 27, floor 16 (SlimeBoss), turn 6: monsters.
- Run 28, floor 10 (FungiBeast + AcidSlime_M), turn 2: free.Anger+.
- Run 28, floor 12 (SpikeSlime_L), turn 6: free.Anger+.
- Run 28, floor 16 (TheGuardian), turn 11: free.Rage+.
- Run 38, floor 5 (SlaverBlue), turn 2: free.gen:Blood for Blood{cost=3/combat}.
- Run 40, floor 13 (Lagavulin), turn 3: monsters[0].powers.Metallicize.
- Run 56, floor 11 (Lagavulin), turn 3: monsters[0].hp.
- Run 70, floor 3 (JawWorm), turn 1: discard.Strike, hand.Strike, monsters[0].hp, player.energy.
- Run 72, floor 7 (Sentry + Sentry + Sentry), turn 3: monsters[0].block, monsters[0].hp, monsters[1].block, monsters[1].hp, monsters[2].block, monsters[2].hp.
- Run 74, floor 16 (SlimeBoss), turn 3: discard.Defend, discard.Defend{cost=0/combat}.
- Run 77, floor 7 (FungiBeast + FungiBeast), turn 3: player.powers.Vulnerable.
- Run 80, floor 8 (FungiBeast + FungiBeast), turn 3: player.powers.Vulnerable.

(819 of 852 engine-played fights had no miss.)

<!-- /GENERATED -->

## Notable fights

- **Slime Boss at Ascension 20, run 39 (floor 16, HP 68 -> 34).** The first A20 Slime Boss win, after three losses.
  A stronger deck than the losses had: Immolate on turn 1 (damage to all, and Burns), Reaper, then Evolve and Fire
  Breathing, so every Slimed or Burn card drawn drew a card and hit all the slimes for 6. The boss's slam cost 38 HP
  (72 -> 34); it split at 47 and the halves fell two turns later. Every predicted step matched.
- **The Guardian at Ascension 20, run 28 (floor 16, HP 87 -> 16).** The first A20 run (the owner asked for harder
  runs; the Act 1 session gave the engine every Act 1 monster's A20 numbers, moves and AI). The AI beat a Gremlin Nob
  elite and The Guardian at A20, with 127 of 130 predicted steps matching the game; all three misses were one
  translator case (a card upgraded in the fight, Anger+ and Rage+, read as free), fixed in 740d5b16. No miss came from
  a monster's ascension numbers.
- **Slime Boss, run 7 (floor 16, no HP lost: 80 -> 80).** On turn 1 the AI played Wild Strike, Perfected Strike,
  Evolve and Fire Breathing+. From then on every Status card it drew (the Wounds Wild Strike shuffles in, the Slimed
  the boss's Goop Spray adds) drew another card and hit every slime for 10. It split the boss at 41 HP, finished the
  two Large slimes the same way, and was never hit.
- **Slime Boss, run 4 (floor 16, HP 70 -> 69, 74 after Burning Blood).** The AI lost 1 HP in the whole fight. A slime
  splits into two smaller slimes that each start with the HP it had when it split, and the AI played to that: it took
  the Spike Slime (L) down to 1 HP before ending the turn, so its split gave two Spike Slimes (M) with 1 HP each, and it
  split the Acid Slime (L) low too (two Acid Slimes (M) with 3 HP each). It blocked the turns the slimes attacked.
  All 26 predicted steps matched the game, splits included.
- **Hexaghost, run 17 (floor 16, HP 52 -> 27).** The day's only Hexaghost, met at 52 HP. The AI started with
  Thorns 3 and played Metallicize+ on turn 1, so the Hexaghost's multi-hit attacks cost it HP on every hit; then it
  raced the boss's 250 HP in 11 turns with Flex-boosted Strikes, Twin Strikes and Rampage, blocking only as needed.
  All 33 predicted steps matched the game.
- **The Guardian, run 2 (floor 16, HP 83 -> 61, 67 after Burning Blood).** The AI built a Demon Form
  win: on turn 1 it used Armaments to upgrade Demon Form and played it (+3 Strength every turn), then Disarm on the
  Guardian (-2 Strength) and Metallicize. By turn 8 it had 21 Strength, so single Strikes and Iron Waves did most of the
  work; it blocked through the Guardian's defensive phases and killed its 240 HP on turn 10.
- **The Guardian, run 1 (floor 16, HP 71 -> 44, 50 after Burning Blood).** 15 turns. While the Guardian was in its
  offensive mode the AI attacked it hard (Shockwave on turn 1 for Weak and Vulnerable, then Bash+ and Strikes) and
  broke its Mode Shift three times. In defensive mode (Sharp Hide 3: each attack played costs 3 HP) it mostly blocked,
  played no attack or one, and used True Grit+ to exhaust Strikes, thinning the deck before the next offensive phase.
  It finished the Guardian with Bash+, Pommel Strike and Swift Strike+ on turn 14.
- **Five slimes, run 1 (floor 12, no HP lost).** Against two Acid Slimes (S) and three Spike Slimes (S) the AI opened
  with Shockwave (Weak 3 and Vulnerable 3 on all five), then killed them over three turns without taking damage.
- **Lagavulin, run 2 (floor 8, the second elite, HP 56 -> 46, 52 after Burning Blood).** It set up Metallicize and Demon Form while Lagavulin
  slept, then killed it in five turns once it woke. All 22 predicted steps matched the game.

## The losses

Run 26 died early, on floor 7: the three-Sentry elite on floor 6 cost 53 HP (72 -> 19), and four gremlins finished it
at 25 HP on the next floor. Every predicted step of both fights matched the game, so this is the play, not the bridge.

Run 30 (Ascension 20) died on floor 7 to Lagavulin: an Acid Slime (L) had cost 33 HP on floor 6, and the map rule
(elites last, but taken when the path offers nothing else) led into the elite at 44 HP. Every predicted step matched.
A rule that weighs an elite against the HP left is run-layer work for later.

Run 33 (Ascension 20) died on floor 12: the three Sentries on floor 8 cost 42 HP (50 -> 8), and on floor 11, at 10 of
75 HP, the map offered a rest site or a fight; the map rule (fights first, rest sites fourth) took the fight, and the
run died in it. Below half HP the map now takes a rest site first (8d7d529a).

Run 37 (Ascension 20, rules 2) died on floor 8: its path held two elites in a row, each the only node offered (the
map rule looks one node ahead), and Gremlin Nob cost 51 HP (57 -> 6) before Lagavulin met it at 22. Every predicted
step matched. Looking further along the path is part of backlog 80's run-layer item.

Run 49 (Ascension 20, rules 2) died on floor 12. On floor 9, at 67 of 75 HP, the map offered an event or a fight,
and the map rule (fights first) took the fight. That branch then held fights on floors 10, 11 and 12, a shop, an
elite on floor 14 and no rest site before floor 15; the event branch reached a rest site on floor 13. Jaw Worm and a
Spike Slime (M) cost 46 HP (67 -> 21: the deck dealt little damage, and Jaw Worm's Bellow reached Strength 15 by turn
9), four gremlins 21 more (27 -> 6, 12 after Burning Blood), and an Acid Slime (L) killed it at 12 HP, where the map
offered only a fight or an elite. Every predicted step matched. Looking further along the path is backlog 80's
run-layer item.

Run 50 (Ascension 20, rules 2) died on floor 8 to Lagavulin. The three Sentries on floor 6 cost 48 HP (67 -> 19, 25
after Burning Blood); then, at 25 of 82 HP with no rest site offered, the map rule took a fight (25 -> 9, 15 after)
over an event, and the only node after that fight was Lagavulin. Every predicted step matched. Replayed under rules 3,
the map takes the event there, whose path reaches a rest site on floor 8.

Run 52 (Ascension 20, rules 3) died on floor 10 to Gremlin Nob. Four gremlins on floor 5 cost 57 HP (79 -> 22, 28
after Burning Blood), and a rest site brought it back to 52. On floor 7 the event rule took the Golden Idol (the word
"gold" scores, though the bot walks past every shop, so gold is worth nothing to it), and its trap cost 8 max HP. On
floor 9, at 52 of 74 HP, both branches held an elite before the next rest site and no path survived the look-ahead's
pessimistic costs, so the rule took the cheapest: Gremlin Nob, one fight and a rest site, over two fights, an elite
and at least two more fights. Nob killed it from 52 HP. Every predicted step matched.

Run 55 (Ascension 20, rules 4) died on floor 6 to three Sentries from 73 HP. The rules-3 look-ahead took the elite
over a rest site (it counted an elite as two card picks), and the deck (the starter with Carnage, Intimidate, Warcry
and Armaments) drowned in Dazed over 14 turns. Every predicted step matched. Rules 5 puts elites last again.

Run 72 (Ascension 20, rules 5, fight guard 1) died on floor 10 to Gremlin Nob from 18 HP. On floor 5, at 45 of 75 HP,
the rest site upgraded a card instead of resting (the rule rests below 60% HP, and 45 is exactly 60%), though every
path from it held two elites before the next rest site; three Sentries then cost it 15 HP (45 -> 30), a fight 9 more,
and the second elite was the only node offered. Every predicted step matched except one Sentry miss (Fire Breathing on a
Curse, under "Not fixed"). A run-layer finding for the batch: rest when the path to the next rest site holds an elite, not by HP alone.

Run 76 (Ascension 20, rules 5, fight guard 1) died on floor 8 to Lagavulin from 56 HP, with Lagavulin at 14 of 114:
both elites on its path were the only node offered (the first cost 45 HP, 77 -> 32; a rest site brought it to 56), and
the 16-card deck dealt about 100 damage in 14 turns while Lagavulin's Siphon Soul stripped its Strength and Dexterity.
Every predicted step matched.

Run 78 (Ascension 20, rules 5, fight guard 1) died on floor 13 to a Looter from 11 HP. On floor 11 the search hit the
engine's power cap and the fallback player finished that fight at a cost of 38 HP (55 -> 17, see "Not fixed"); the
map then offered only fights (three lice took it to 5, 11 after Burning Blood) and no rest site. Every step the
engine predicted matched.

Run 79 (Ascension 20, rules 5, fight guard 1) died on floor 10 to Lagavulin from 62 HP on turn 12, with Lagavulin at 5
of 114; both of its elites were the only node offered. Like run 76, the deck dealt too little damage before Siphon Soul
stripped its Strength and Dexterity. Every predicted step matched.

Run 83 (Ascension 20, rules 5, fight guard 1) died on floor 7 to Lagavulin from 36 HP, after an 84-turn fight on
floor 5 against four gremlins (60 -> 8 HP). From turn 4 on, a Shield Gremlin at 4 HP shielded a Mad Gremlin with 11
block each monster turn, and each turn the search rated striking into that block (1.494) above the Strike that would
kill the Shield Gremlin (1.474), so it hit the block again and again until turn 83. It is play: the engine's Protect
timing did differ on turns 2-3 (Flame Barrier was up, and the search overrated it by about 4 HP; the comparison
misses it, see below), but not later, where the stall happened. Within two turns killing the Shield Gremlin gains little, while the cost of
a protector re-blocking its ally every turn builds up past the horizon, and the net has no input for the Protect
intent. The fight guard doesn't help (no single action wins the fight); backlog 85. Every
predicted step matched. A fighter finding for the product (with backlog 82), and a bridge stopgap to weigh: hand a fight
that passes a turn limit to the fallback, which strikes the first living monster.

### The boss losses

At Ascension 20 the bosses so far: Slime Boss beaten 15 of 20 times, Hexaghost 4 of 17, The Guardian 11 of 14 (runs
28-90; run 90 (rules 5, fight guard 1) lost to Hexaghost from 43 HP; run 89 (rules 5, fight guard 1) beat Slime Boss 76 -> 44; run 88 (rules 5, fight guard 1) beat The Guardian 78 -> 55; run 87 (rules 5, fight guard 1) lost to Hexaghost from 70 HP; run 86 (rules 5, fight guard 1) beat Slime Boss 66 -> 31; run 85 (rules 5, fight guard 1) lost to Hexaghost from 48 HP; run 84 (rules 5, fight guard 1) beat Slime Boss 82 -> 58; run 82 (rules 5, fight guard 1) lost to Hexaghost from 68 HP on turn 10, with the boss at 62 of 264; run 81 (rules 5, fight guard 1) beat The Guardian 73 -> 31; run 80 (rules 5, fight guard 1) lost to Hexaghost from 77 HP on turn 11, with the boss at 95 of 264; run 77 (rules 5, fight guard 1) beat The Guardian 81 -> 23; run 75 (rules 5, fight guard 1) beat The Guardian 82 -> 69; run 74 (rules 5, fight guard 1) beat Slime Boss 58 -> 24; run 73 (rules 5, fight guard 1) beat Hexaghost 67 -> 24; run 71 (rules 5, fight guard 1) beat Slime Boss 60 -> 33; run 70 (rules 5, fight guard 1) beat Slime Boss 84 -> 44; run 69 (rules 5, fight guard 1) lost to The Guardian from 44 HP on turn 6, with the boss at 187 of 250, after
Gremlin Nob (every next node was an elite) cost 39 HP and a floor-14 fight 38 (on its turn 6 the guard played the
winning blow the search passed); run 68 (rules 5, fight guard 1) beat The Guardian 71 -> 22; run 67 (rules 5, fight guard 1) beat The Guardian 62 -> 30; run 66 (rules 5, fight guard 1) beat The Guardian 58 -> 34; run 65 (rules 5, fight guard 1) lost to Slime Boss from 77 HP on turn 10, with 52 HP of slime left; run 64 (rules 5, fight guard 1) beat Slime Boss 66 -> 40; run 63 (rules 5, fight guard 1) beat Slime Boss 68 -> 39; run 62 (rules 5, fight guard 1) lost to Hexaghost from 77 HP on turn 9, with the boss at 61 of 264; run 61 (rules 5, fight guard 1) lost to Hexaghost from 66 HP on turn 7, with the boss at 28 of 264; run 60 (rules 5, fight guard 1) beat Slime Boss 75 -> 41; run 59 (rules 5, fight guard 1) beat Slime Boss 60 -> 49; run 58 (rules 5, fight guard 1) lost to Hexaghost from 77 HP: Divider hits for HP / 12 + 1 each, so the full HP
it brought made it 7 x 6 (77 -> 38), and it died on turn 8 at 11 HP (Sear and two Burns) with the boss at 68 of
264; run 57, the first on rules 5, beat Slime Boss 90 -> 59, after one elite (the only node offered) and passing two
it could skip; run 56 (rules 4) lost to Slime Boss from 38 HP: it had fought three elites, and on floor 14 the search left a Blue
Slaver at 6 HP for ten turns (75 -> 5 HP; see Fight guard 1); run 54 (rules 4) lost to Hexaghost from 64 HP after beating Gremlin Nob without a hit: its turn-9 Inferno
took 32 HP (39 -> 7) and it died on turn 11 with the boss at 116 of 264. The Hexaghost losses are damage races: by
the turn-9 Inferno runs 48, 53 and 54 had dealt 155, 194 and 138 of the boss's 264 HP at A20; run 53 (rules 3) lost to Hexaghost from 69 HP the way run 48 did: Divider and the hits after it brought it to
31 by turn 5, and the turn-9 Inferno killed at 15 HP with the boss at 70 of 264; run 51, the first on run rules 3, beat Hexaghost 76 -> 18 after eight hallway fights and no elite (it passed
two elites the map offered at 71 and 74 HP); run 48 lost to Hexaghost from 67 HP: its Divider took 31 HP on turn 2 and its turn-9 Inferno (6 x 6 with
Strength 3) killed at 20 HP with the boss at 100 of 264; run 47 beat Slime Boss 68 -> 52; run 46 beat The Guardian 71 -> 32; run 45 lost to Hexaghost from 50 HP after a Gremlin Nob; run 44 beat Slime Boss with 3 HP left; run 38 lost to The Guardian from 61 HP; run 40 beat it with 8 HP left; run 41 beat Slime Boss from 85 HP;
run 42 beat The Guardian 66 -> 37; run 43 lost to it from 50 HP after two elites). Every predicted step of those boss fights matched the game, so the engine plays A20 faithfully; the gap is
the play. The net was trained on Ascension 0 fights.

Run 36 (Ascension 20, rules 2) lost to Slime Boss from 64 HP after the Sentries (64 -> 24) and a quiet end of the act.

Run 35 (Ascension 20, rules 2) lost to Hexaghost from 70 HP after a clean Act 1 (a Gremlin Nob elite and nine
hallway fights, every predicted step matched, 138 of 138).

Run 34 (Ascension 20, rules 1) lost to Slime Boss from 49 HP. It had spent floors 11 to 14 low (down to 3 HP after
three Fungi Beasts), under the map rule from before the rest-site change. Every predicted step matched.

Run 32 (Ascension 20) lost to Slime Boss from 64 HP with a 14-card deck still close to the starter (five Strikes, four
Defends, Ascender's Bane, Bash+, Perfected Strike, Infernal Blade, Clothesline, Blood for Blood). The boss's attack
between turns 3 and 4 cost 33 HP (64 -> 31); it split the boss at 80 HP and fought the smaller slimes down, but died on turn 9 with an
Acid Slime (L) left. Every predicted step matched.

Run 16 lost to The Guardian after a controller bug (Blood for Blood after Sharp Hide, below) handed the fight to the
fallback player on turn 4 at 75 HP.

Run 8 reached The Guardian with 51 HP and a thin deck (four Strikes, four Defends, Bash+, Anger+, Heavy Blade,
Clothesline and few other attacks). It played Combust on turn 2, which cost 1 HP on each of the fight's 15 turns, and
spent several turns upgrading Defends with Armaments. It died with the Guardian at 64 HP.

### Slime Boss at Ascension 20

The three A20 Slime Boss losses (runs 32, 34, 36) against the seven A0 Slime Boss wins (runs 4, 7, 10, 11, 12, 24,
27), from the recorded fights:

| Run | Asc | HP at start | Boss split (turn, boss HP) | Most Slimed at once | Worst monster turn | HP lost | Potions used | Result |
|---|---|---|---|---|---|---|---|---|
| 4 | 0 | 70 / 74 | 4, 36 | 3 | 1 | 1 | 1 | won |
| 7 | 0 | 80 / 80 | 4, 41 | 3 | 0 | 0 | 0 | won |
| 10 | 0 | 62 / 80 | 4, 56 | 3 | 0 | 0 | 1 | won |
| 11 | 0 | 74 / 80 | (not read) | 3 | 35 | 35 | 1 | won |
| 12 | 0 | 85 / 85 | 4, 50 | 3 | 1 | 4 | 1 | won |
| 24 | 0 | 85 / 85 | 4, 70 | 7 | 11 | 32 | 1 | won |
| 27 | 0 | 81 / 88 | 4, 70 | 3 | 6 | 0 (Reaper healed) | 1 | won |
| 32 | 20 | 64 / 82 | 6, 42 | 14 | 33 | 64 | 0 (none held) | lost |
| 34 | 20 | 49 / 80 | 4, 60 | 9 | 18 | 49 | 0 (none held) | lost |
| 36 | 20 | 64 / 75 | 5, 54 | 9 | 25 | 64 | 1 (all it held) | lost |

At A20 the boss has 150 HP (140 at A0). The losses arrived with less HP (49 to 64), held 9 to 14 Slimed cards at
once (3 in six of the seven wins), and single monster turns cost them 18 to 33 HP, where the wins mostly lost 0 to 11
(run 11's 35 is the exception). The split came about when it does at A0 (turn 4 to 6, boss at 42 to 60 HP). No turn
in these fights ended with energy and a playable card (other than Slimed) left, and no potion was left unused. So
the numbers show no clear blunder: the gap is the HP the run brings and the damage the boss deals, which a net
trained on A0 fights doesn't price. Which slime it attacked after the split isn't read here. Three losses is a small
sample.

## Act 2

From run 21 on, a run stops when Act 2 starts (the owner's call: the engine doesn't model Act 2, so playing it on
the fallback only costs time). The controller records the run as stopped there, closes the game and deletes its own
save; a launch loop starts the next run on a fresh game, which also loads the newest code and content each time.

Before that:

The engine models Act 1 only, so each Act 2 fight is played by the simple fallback player (first playable card on the
first living monster). Every run that beat its Act 1 boss died later in Act 2, between floors 21 and 31 (run 9, whose
boss relic Pandora's Box had turned its Strikes and Defends into other cards, went furthest); Centurion + Healer ended
two of them.

## Decision times

Most decisions take under a second. The slow ones (10 to 40 s) come with chance-heavy cards: Havoc (a random top
card), True Grit (a random card exhausted) and potions that offer random cards (Colorless Potion, Skill Potion), where
the search averages over many outcomes. Run 2's decisions on floors 11 to 14 were also slowed (up to 110 s) by a wheel
build running beside the game.

## Bugs the live runs found

Fixed (each with a test in `scripts/tests/test_real_game.py` or `test_real_game_run.py`; a fix loads at the next game
start):

- **Liquid Memories after Rampage (run 1, floor 10, fallback).** The AI played Rampage and, within the same second,
  drank Liquid Memories to take it back from the discard pile at cost 0. The game's card-flight animation was still
  carrying Rampage to the discard pile; when it landed it reset the card's cost (`Soul.update` calls `clearPowers`),
  so the game showed Rampage at cost 1 and wouldn't play it, while the engine thought it was free. The translator now
  keeps the engine's "free this turn" marks only on hand cards the game shows at cost 0. The same race wasted a
  Liquid Memories on Blood for Blood in run 38, so the controller now sends CommunicationMod's `wait 30` before a
  potion that comes right after a play, and the card lands first (ec58a07d).
- **Rampage's damage lost in a shuffle (run 1, floor 14, prediction miss).** Rampage gains 5 damage each time it is
  played in a fight. The translator moved that mark by pile, so when the discard pile was shuffled into the draw pile
  the mark was dropped and the engine predicted 8 damage instead of 13. The controller now keys the mark by the game
  card's `uuid` when it plays the copy, so the mark follows the card through shuffles, and a play of the marked copy
  picks that copy in the game's hand.
- **Cards played this turn (runs 1 and 2, prediction misses).** A card Havoc plays counts as played this turn in the
  game and in the engine, but the controller counted only its own plays. The game doesn't show this number; the view
  now takes the engine's own count.
- **The death screen (run 1, floor 22, the run sat idle).** The game shows its game-over screen while the room is
  still in combat, and the controller treated it as part of the fight, where it had nothing to send. It now records
  the run and proceeds. Because of this, run 1's last fight (Centurion + Healer) is missing from its fight list.
- **Havoc into a pick (run 2, floor 13, fallback).** Havoc+ played the top card, which was Armaments, and the game
  opened Armaments' pick. The step has chance in it, and the controller's kept prediction had played a different card,
  so it had no pick to answer. It now takes the predicted sample whose pick offers the game's cards.
- **The fight record's end HP (records before eff55bc5).** The game's first state after a fight already includes
  Burning Blood's heal, so the old `hp_end` was the HP after the fight and a boss fight could read as HP gained
  (Slime Boss 70 -> 74). Fights now record both (`hp_end`, `hp_after`); the report takes the end HP of older fights
  from their last state in `states.jsonl`.
- **Snecko Oil (run 4, floor 10, Lagavulin, fallback).** The potion rolls each hand card's cost for the rest of the
  fight. The translator copied the cost marks from the engine's own prediction, which had rolled other costs, so the
  plan asked for a 0-cost Strike the game didn't have. Cards now carry the cost the game shows wherever it differs from
  the card's master-deck copy; a card free this turn stays "free this turn", and costs the engine works out itself
  (Corruption's skills, Blood for Blood) are left to it.
- **Blood for Blood after Sharp Hide (run 16, The Guardian, fallback; the run was lost; engine rule).** The
  Guardian's Sharp Hide hit the player for 3 when Blood for Blood+ was played. In the game each HP loss drops by 1 the
  cost of the copies in the hand, draw and discard piles only (`AbstractPlayer.updateCardsOnDamage` ->
  `tookDamage`); the card in play is in limbo while that damage lands, so its own cost doesn't drop. The engine kept
  one HP-loss count for every copy, thought the copy cost 1 where the game showed 2, and its planned play was refused.
  The fallback finished the boss fight from 75 HP and lost. Each copy now carries its own cost for the combat (a
  changed copy), dropped where the game drops it; the count is left only for copies made in the fight (`makeCopy`),
  and an upgrade keeps a copy's drops (`BloodForBlood.upgrade`: cost - 1). The translator names each copy by the cost
  the game shows (`engine/tests/cost_changes.rs`; no golden change). Blood for Blood is the only "cost drops when X"
  card the Act 1 packs and `content/cards.json` load (Eviscerate, Masterful Stab, Streamline and Force Field belong
  to other characters).
- **A pick answered from the wrong sample (run 15, Warcry+, prediction misses).** Warcry+ draws two cards and then
  puts one back on the draw pile. The controller took the first predicted sample whose pick offered only cards the game
  offered too, and a sample that had drawn two Defends passed, so its plan put back the wrong card. The controller now
  prefers the sample whose piles are the game's.
- **A power without an amount (run 14, prediction miss).** A Power Potion gave Barricade; the game lists powers
  without an amount as -1, and the engine holds them as 1. Amount -1 now reads as 1, except for powers that really go
  negative (Strength, Dexterity, Focus).
- **A potion's card at cost 0 (run 13, The Guardian, prediction miss).** A Skill Potion gave Seeing Red, free this
  turn; it isn't in the master deck, so the translator had no base cost to compare, and the engine's own sample had
  made another card. A hand card made in the fight that the game shows at cost 0 now gets the engine's free mark.
- **Art of War's hidden counter (run 12, Lagavulin, prediction misses).** The game shows no counter for Art of
  War (-1) and the translator wrote 0 over the engine's flag. Where the game shows no counter, the view now keeps the
  engine's value.
- **A free card in the discard pile (run 10, floor 5, prediction miss).** A Strike made free by Liquid Memories
  and played showed cost 0 in the discard pile until its flight there landed, and the translator read that as a
  cost mark. The controller now remembers the free copies it played this turn and ignores their shown cost outside
  the hand until the turn ends.
- **A pick of one card the engine took itself (run 8, floor 12, fallback).** Armaments upgrades a card in hand;
  with two Defends in hand the engine has one option and upgrades without asking, but the game still opens its pick.
  The controller now answers such a pick with the first copy.
- **From a review of the run layer (no live failure yet):** a multi-card grid (Empty Cage, Astrolabe, Neow's "remove
  2") would pick and unpick the same card forever; the run mark that lets the controller replace its own save stayed
  after the run, so a later save of the owner's could have counted as ours; an error other than a known hand-over left
  the game waiting with no answer; the card-reward memory carried into the next run.
- **Perfected Strike played by Havoc (run 1, The Guardian, turn 12; engine rule).** Perfected Strike deals 2 more
  damage for each Strike card in the hand, draw and discard piles. Played from the hand it counts itself (the game
  computes its damage while it is still in the hand); played by Havoc, or as Double Tap's copy, it is in limbo and
  doesn't. The engine always counted it, predicting 21 damage where the game dealt 18. The engine now counts the card
  in play only when it was played from the hand (`InPlay::queued`, stored in the state encoding).
- **The Guardian's Mode Shift broken by Combust at the end of the turn (run 8, turn 7; engine rule).** When the
  Guardian's Mode Shift runs out it queues its change to Defensive Mode (`ChangeStateAction`) at the bottom of the
  game's action queue, and that change queues its 20 block behind it. Broken by an attack during the player's turn,
  the block lands after the card and is lost when the monsters' turn starts. Broken by Combust's end-of-turn damage,
  the change runs after the turn end has queued `MonsterStartTurnAction`, so the block lands after the monsters'
  start-of-turn block loss and the Guardian keeps it into the player's next turn (game: 20 block; the engine had 0).
  The engine now puts monster block the game queues behind what is queued now in `deferred_block` while the turn
  ends too (a transient `turn_ending` flag, or `Stage::EndingTurn`), and `monsters_turn` lands it after clearing the
  monsters' block (`engine/tests/act1_bosses.rs` `guardian_shift_at_turn_end_keeps_its_block`; no golden change).
- **Regeneration heals before other turn-end effects (run 12, Lagavulin; engine rule).** The game's Regeneration
  queues its heal at the top of the action queue (`addToTop`), so at the end of the turn it heals first and Combust's
  HP loss comes after; the engine ran turn-end hooks in order and lost the HP first. With HP near its maximum the
  results differ by the heal the cap cut off (game 84, engine 85). A hook may now carry `acts_first`
  (docs/extending.md): within its turn-end pass it acts before the hooks called earlier, the last called first.
  Regeneration and Orichalcum carry it, the only Act 1 powers and relics whose end-of-turn methods use `addToTop`
  (`engine/tests/turn_end_first.rs`).
- **Feed's max HP (run 16, floor 14, prediction miss; content).** The content pack's Feed only dealt 10 damage; the
  game's `FeedAction` also raises max HP by 3 (4 upgraded) and heals as much when the hit kills a target that isn't
  half dead or a minion. Content now has a general on-kill condition, `TargetDied` (the chosen target died to the card
  in play), and Feed carries a row of it with `GainMaxHp`. When the kill wins the fight, the gain lands before the
  combat-end relics, as the game's does inside its action (`engine/tests/kill_effects.rs`; no golden change). The
  jar's other on-kill actions belong to cards outside Act 1 combat: Hand of Greed's gold is run-layer only, Ritual
  Dagger comes from an Act 2 event, Sunder and Lesson Learned are Defect and Watcher cards. The gauntlet still keeps a
  fixed max HP between fights, so a simulated run drops Feed's gain after the fight.
- **Tungsten Rod and a card's own HP cost (run 23, floor 12, prediction miss; translator).** Hemokinesis costs 2 HP;
  with Tungsten Rod the game took 1 (the relic's `onLoseHpLast` cuts every HP loss by 1, a card's cost included),
  the engine took 2. The engine's rule was already the game's (`HpLossLast` runs on every loss, `LoseHp` included;
  `engine/tests/after_block.rs`); the translator lost the relic: the engine holds Tungsten Rod as a power the game
  doesn't show, and the turn-1 priors took the player's powers from the game's view, so no view of any fight held it
  (Torii, The Boot, Calipers, Paper Phrog, Odd Mushroom, Ginger, Turnip, Strike Dummy, Blue Candle and Medical Kit
  the same way). The turn-1 priors now keep the hidden powers a fresh fight starts with. A check of every HP-loss
  hook against the jar found one engine rule off: Rupture (`wasHPLost`, `info.owner == owner`) also counts the
  player's own Burn and Decay damage (`DamageInfo(player, 2, THORNS)`); the engine counted it as someone else's.
  Damage a creature deals itself now counts as its own loss (`HpLossFrom::Card`). Tungsten Rod, Buffer (every
  loss), Torii, Angry, Curl Up, Plated Armor (NORMAL damage with an owner), Self-Forming Clay, Centennial Puzzle,
  Runic Cube, Red Skull (`onBloodied`) and Blood for Blood's drop (every loss) already matched (`after_block.rs`; no golden change).
- **Lagavulin's wake with extra Metallicize (run 40, the burning elite, prediction miss; engine rule).** When
  Lagavulin wakes the game removes 8 Metallicize (`Lagavulin.changeState("OPEN")`: `ReducePowerAction(..., 8)`); the
  engine cleared it. They agree on the usual 8, but this was the map's burning elite, buffed with +4 Metallicize (12
  in all), so the game kept 4 and the engine 0. The wake now takes 8 off (a negative Apply of an official
  non-negative power acts as `ReducePowerAction`), and fights can carry a burning elite's buff (`elite_buff` on
  `Combat` and `sts.run` specs) (e48f16f9; `engine/tests/monsters_act1.rs`; golden gains the cover game
  `cover-lagavulin-burning`, rules version 696d607bbb413f47).
- **The burning elite's Regenerate (run 56, floor 11, Lagavulin, prediction miss; engine rule).** The fourth
  burning-elite buff, `RegenerateMonsterPower` (game id `Regenerate`, 2n+1 so 3 in Act 1, a `HealAction` of its amount
  at the monster's `atEndOfTurn`), had no engine power, so the bridge left it out (the fight record lists "power
  Regenerate on Lagavulin") and one prediction missed Lagavulin's HP by the 3 it healed (43 against 46). It is
  now the pack power `Regenerate` of `content/packs/act1-monsters.json` (one `OwnerTurnEnd` hook healing its owner by
  its stacks), bound into a fight only when it is the buff (`EliteBuff::Regenerate`, `elite_buff="regenerate"`),
  and `content/game_ids.json` maps the game's id to it, so `Combat.from_view` rebuilds such a fight
  (`engine/tests/act1_packs.rs`; no golden change).

- **A potion sent twice (run 70, floor 3, Snecko Oil, fallback; translator).** The controller sent `potion use 0`;
  the game's next state still showed Snecko Oil in its slot with the same hand and energy, as if the potion had not
  acted, so the controller planned again and sent the potion a second time. The potion had acted by then, so the game
  refused the command and the fight went to the fallback (won, 72 -> 68). Now a state that still shows the potion
  with nothing else changed after a potion command gets `wait 30` (at most three, then `state`) instead of a new plan
  (`test_a_state_from_before_the_potion_gets_wait`).

- **Fire Breathing on a Curse (run 72, floor 7, the burning Sentries, prediction miss; engine rule).** The game's
  `FireBreathingPower.onCardDraw` fires on a Status or a Curse; the engine fired it on Status draws only. Turn 3's
  draw took Ascender's Bane, so the game hit each Sentry for 10 through its 4 Metallicize block (38/24/39, no block)
  where the engine predicted 44/30/45 with 4 block. Fixed by the Act 1 session in 100444cc (rules version
  d08bc2b781dd64da); run 72's turn now gives the game's numbers.

- **A monster's debuff applied during the player's turn, and Shield Gremlin's Protect (runs 77 and 83, prediction
  miss and an uncompared difference; engine rule).** A Fungi Beast killed on the player's turn gave Vulnerable 2 that
  the game ticked down at the round's end (the game holds a monster's debuff back only when it lands after the turn
  has ended); the engine held it. And the engine landed Protect's block at a different moment than the game, which
  run 83's turns 2-3 showed (not counted, being a chance step). Both fixed by the Act 1 session in 378e2a40 (rules
  version 334dd4b4ef071632, with the game's 999 caps); runs 77's and 83's turns now give the game's numbers.

- **The engine's power cap in a search (run 78, floor 11, fallback; engine).** The search panicked with "a creature
  holding 12 powers (POWER_CAP) gained a new one": a looked-ahead line with Dead Branch's random cards stacked more than
  12 powers on one creature. The controller caught it and handed the fight to the fallback (won, 55 -> 17). The game
  has no such cap; since 70240961 a creature holds any number of powers (rules version unchanged), and run 78's
  decision now searches to the end.

Not fixed:

- **A Defend free for one turn read as free for the fight (run 74, Slime Boss, turn 2 -> 3, prediction miss;
  translator).** During turn 2 a Defend in hand showed cost 0; the game reset it to 1 when it went to the discard
  pile at the turn's end, while the bridge had marked it 0 for the rest of the fight (`Defend{cost=0/combat}`). What
  made it free that turn isn't read yet; a turn-only cost needs telling apart from a combat-long one.
- **A pick after several random cards (run 22, Distilled Chaos, prediction miss).** Distilled Chaos plays the draw
  pile's top three cards; when one of them asks for a pick (Armaments), the controller answers from a predicted sample,
  and with three random cards none of the 32 samples may hold the game's cards, so it takes the closest. The pick is
  sensible but the step is recorded as a miss. Fix: let `Combat.from_view` rebuild a fight paused at a pick, so the
  controller can answer from the game's own state (backlog 79, view-at-a-pick, with the Havoc and Warcry+ cases).

- **Runic Dome hides the enemies' moves (run 6, Act 2).** The run layer took the first boss relic offered, and in
  run 6 that was Runic Dome, which hides every enemy intent: the game then sends no move ids, so the translator can't
  rebuild any fight. Run 6 died to three Cultists, monsters the engine models, under the fallback. The boss-relic rule
  now skips Runic Dome (34064599, from run 8 on); reading hidden moves from the engine's own prediction is not done.

- **A Cultist without a shown move (run 2, floor 25, Act 2, no Runic Dome).** The game listed a Cultist with no
  move yet; the translator needs a move to rebuild a monster. Act 2 fights go to the fallback anyway.
