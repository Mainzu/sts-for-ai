# The real-game bridge

Status: building (2026-11-13, steps 1-5 built, 75d57fa6..65ef0fb2, checked offline against a fake game; step 6 and the live run wait for 14 Nov. As built: README "Real-game bridge").

Step 7 queued as job 1014. Changes from this text: the launcher also
writes `runAtGameStart=true` (the mod's default is false) and raises
`maxInitializationTimeout` to 30; move numbers map to engine move
positions, several where the engine counts a cycle
(`content/game_ids.json`), and the engine's own last prediction picks
among them.
Builds on the product player (`product/net`, `docs/specs/line-step.md`),
the relic entity (`docs/specs/relic-entity.md`) and potions
(`docs/specs/potions.md`).

## Outcome

The product plays fights in the real Slay the Spire on the owner's laptop.
The owner starts an Ironclad run and clicks through the map, events, shops
and rest sites. Whenever a fight is on, the AI plays it through
CommunicationMod, using the same search and net as the headline player,
and records every decision. Card rewards are picked by the AI too, if
step 6 is built in time.

**How it moves the goals.** Goal 2: the first time the product meets the
real game, rather than our engine's copy of it. Two numbers come out of it:
how the AI does in real fights, and how often the engine predicted the
game's next state exactly ("fidelity"). Both go on the showcase site on
14 Nov. Nothing in the engine's rules changes, and no headline number or
existing net moves.

**Non-goals:**
- The run layer: map, events, shops, rest sites, Neow, potion and relic
  rewards. The owner plays those by hand.
- Characters other than Ironclad, acts past Act 1, Ascension above 0.
- Starting or abandoning runs from the bridge. The bridge never sends
  `start`, and it sends nothing outside a fight (or a card reward, step 6).
- Speed work on the search. The decision time is measured and reported,
  not tuned.

## Behavior

### Launching the game (`scripts/real_game.py launch`)

ModTheSpire loads only the mods named for one launch, without its launcher
window:

    <game>/jre/bin/java.exe -jar <workshop>/1605060445/ModTheSpire.jar
        --skip-launcher --mods basemod,CommunicationMod

This runs from the game folder
(`C:/Program Files (x86)/Steam/steamapps/common/SlayTheSpire`) while Steam
is running. ModTheSpire 3.30.3 saves the owner's mod lists
(`%LOCALAPPDATA%/ModTheSpire/mod_lists.json`) only from that launcher
window (`ModSelectWindow`, checked with javap), so the owner's lists and
their next normal launch stay as they are.

Guards, in this order:
1. Refuse if the game is already running (a `java.exe` whose command line
   names `ModTheSpire.jar` or `desktop-1.0.jar`).
2. Back up the game's `saves/` and `preferences/` folders and
   `mod_lists.json` into
   `%LOCALAPPDATA%/sts-for-ai/real-game-backups/<yyyymmdd-hhmmss>/`, keeping
   the newest 20.
3. Write CommunicationMod's own config
   (`%LOCALAPPDATA%/ModTheSpire/CommunicationMod/config.properties`): only
   its `command=` line, set to this repo's Python and
   `scripts/real_game.py play <player>`. Every other file is only read.
4. After the game exits, compare `mod_lists.json` with the backup. If it
   changed, put the backup back and say so.

### The controller (`scripts/real_game.py play <player>`)

CommunicationMod starts this process and talks to it over stdin and stdout:
the mod writes one JSON game state per line, and the controller answers with
one command per line. So stdout carries only commands. Everything else
(logs, records) goes to files.

At each state:
- **Not in a fight**, or not the player's turn: send nothing and wait for
  the next state. The owner is clicking.
- **In a fight the engine can play** (below): rebuild the fight as an engine
  `Combat` from the state, pick an action with the product's policy, and
  send it as a command.
- **In a fight the engine can't play**: write one line saying why (for
  example "card Rampage+ not loaded") to the log and to a small status file
  the owner can watch, then send nothing for the rest of that fight. The
  owner plays it by hand.

### From the game's state to an engine fight

A new engine function builds a fight from a description of a mid-fight
state (a "view"), and `Combat.view()` writes the same description back.
The view holds:
- the player's HP, max HP, block, energy, powers, relics with their
  counters, and potions;
- the hand, the draw pile, the discard pile and the exhaust pile, as card
  names with `+` for upgrades. The draw pile is a set, never an order:
  CommunicationMod lists it in its true order, which a player can't see, so
  the translator sorts it before use;
- each monster's kind, HP, max HP, block and powers, its shown move, and
  its earlier moves this fight (the controller keeps each fight's move
  history from the states it saw; the game sends only the last two);
- the turn number, and the cards played this turn.

Names are translated with tables from the game's own ids to the engine's
names: cards, monsters (with each monster's move numbers, read from its
class in `desktop-1.0.jar`, e.g. Jaw Worm: Chomp 1, Bellow 2, Thrash 3),
powers, relics and potions. A test checks the tables against the game jar.

Content the engine doesn't load:
- **A card or a monster** it doesn't know: the engine can't play the fight
  (above).
- **A relic, potion or power** it doesn't know: the fight is played anyway,
  without it, and the record names what was left out (decision 1). The
  controller rebuilds the fight from the game at every decision, so what a
  missing relic already did shows up in the state (block, Strength, HP).
  Only its future effects are unseen.

### From the engine's choice to game commands

The policy is the product's, unchanged: `depth_paired.decide` at the
product's settings, and while the two-turn tree had no cut, its whole
principal line (line-step). The per-decision part of `guarded_fight` is
moved into a function that both `guarded_fight` and the controller call,
so the two can't drift apart.

Each engine action becomes one command: a card play by its position in the
game's hand (the engine's hand order isn't the game's, so it's matched by
card name and upgrade), with its target slot; using a potion; ending the
turn; answering a card choice (Armaments, True Grit+, Headbutt and the
like) with the card the engine's line picked.

After each command, the controller reads the game's next state and checks
it against the engine's prediction, by comparing views:
- **Same state:** continue the planned line.
- **A chance event** (a draw, the monster turn) or **a different state:**
  record the difference if there was one, then rebuild from the game's
  state and search again.

The fidelity number is the share of predicted (non-chance) steps where the
game's state matched the prediction.

### Records

`results/real-game/<yyyymmdd-hhmmss>/` (gitignored, like all of
`results/`): `states.jsonl` (every state the mod sent), `decisions.jsonl`
(per decision: the view, the options with their one- and two-turn values,
the pick, the time it took), `fights.jsonl` (per fight: monsters, HP before
and after, won, handed over and why, content left out, fidelity counts) and
`log.txt`. The explorer can show these fights later. This is not part of
this spec.

## Decisions to confirm

1. **Unknown relics, potions and powers:** play the fight without them and
   record it (recommended), rather than handing the fight over. Only 47 of
   141 relics load, so handing over would give the AI few fights after the
   first relic.
2. **Card rewards:** the AI picks them with the sim chooser (step 6), but
   only after fights work live. Until then, the owner picks.
3. **The player:** the product (`product/net`) unless today's read
   (step 7) picks the pack-trained net. The controller takes any player
   string.
4. **Parity source:** the installed game's own jar becomes the first place
   to check content against (`javap` on `desktop-1.0.jar`, version
   2022-12-18). `decision/parity-source` says "no install", which is out
   of date.

## Outside assumptions (checked at the start of the build)

- CommunicationMod 1.2.1 (workshop 2131373661) sends a state whenever the
  game is stable after a change, including the owner's own clicks, and
  accepts `play`, `end`, `choose`, `potion`, `proceed` and `state`. Its
  field names are read from its classes with javap, not from memory.
- The human can still click while the controller waits.
- CommunicationMod starts the `command=` process when the game starts.

## Verification

- **Round trip (engine, no game):** for fights over every Act 1 encounter
  the engine loads, played with random legal actions, at every decision
  `from_view(c.view())` gives the same view and the same legal options,
  and stepping either state with the same action and RNG gives the same
  view. Rust and Python tests.
- **Name tables:** every card, monster, move, power, relic and potion the
  engine loads either has a game id or is listed as engine-only, and every
  game id in the tables exists in `desktop-1.0.jar`.
- **Translator:** fixture states written to CommunicationMod's format
  (field names from its classes) for the starter deck against Jaw Worm,
  Gremlin Nob, Lagavulin asleep, the three Sentries, Hexaghost mid-cycle and
  a hand with a card choice. Each translates to the expected view; a
  fixture with an unknown card hands the fight over; one with an unknown
  relic plays and records it.
- **Same policy:** `guarded_fight` plays a fixed set of fights to identical
  results before and after the per-decision part moves out
  (`series_check`).
- **Launcher:** against a fake game folder, it refuses while a fake game
  runs, makes the backup, writes only `command=`, and restores a changed
  `mod_lists.json`.
- **Live (14 Nov, the machine free):** at least one full Act 1 run with the
  AI playing every fight it can. Reported: fights played and won, HP lost,
  handed-over fights and why, the fidelity share, and the median and worst
  decision time.

## Build steps

1. Engine: the view and `from_view`, with the round-trip tests.
2. Name tables from the game jar, with their test.
3. The translator from CommunicationMod states to views, with fixtures.
4. The controller: the shared per-decision policy, commands, the line check
   against the game's state, hand-over, records.
5. The launcher with its guards and the fake-folder test.
6. Card rewards with the sim chooser (decision 2): after step 4 works live.
7. The player read: the product against the pack-trained net on the
   real-content setting (pack cards in the offers, pack hallway monsters),
   queued as an ordinary job today.

Steps 1-5 and 7 run beside the research on 13 Nov. No game runs before
14 Nov.
