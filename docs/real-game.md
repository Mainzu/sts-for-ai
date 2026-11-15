# Playing the real game

The AI can play a real Slay the Spire run through CommunicationMod, a mod
that lets an outside program read the game and send it moves. This page
covers starting the game, letting the AI play whole runs, and reading the
results.

## Real-game bridge

The product plays the fights of a real Slay the Spire run on this dev machine
through CommunicationMod (docs/specs/real-game-bridge.md). Start the game
with only BaseMod and CommunicationMod (your ModTheSpire lists are left as
they are; saves, preferences and `mod_lists.json` are backed up first):

```bash
.venv/Scripts/python scripts/real_game.py launch runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt@hpe0.01@tsl1@lcb1
```

Add `--runs N` to the player tokens to have the controller play N whole
Ironclad runs by itself (`--ascension A` starts them at ascension A, 0-20;
each run's record and the report keep its level; `--act1-only` stops each
run when Act 2 starts, since the engine models Act 1 only, and closes the
game there, since CommunicationMod can't abandon a run; after a death the
next run starts in the same game. So `launch --loop <player> --runs 1000
--act1-only` plays run after run, relaunching the game only after an Act 2
stop, until `results/real-game/stop-loop` exists: the controller then
starts nothing more at the main menu and closes the game) (map, events, rewards and card picks by
`scripts/real_game_run.py`'s rules; it starts a run only while no Ironclad
save of yours exists). `results/real-game/<stamp>/status.txt` says what it
is doing (or why it handed a fight to the fallback player); `fights.jsonl`,
`decisions.jsonl`, `states.jsonl`, `runs.jsonl` and `log.txt` are the
record (gitignored, kept). The controller loads its code only at game
start: create `results/real-game/hold` to have it wait at the main menu
after the current run, then restart the game (delete the file first).
`python scripts/real_game_report.py --write` writes the record's tables
into `docs/research/real-game-runs.md`.
Backups: `%LOCALAPPDATA%/sts-for-ai/real-game-backups/` (newest 20 kept);
`scripts/real_game_launch.py restore-mod-lists` puts the mod lists back.
Name tables: `content/game_ids.json`, checked against the game's jar by
`scripts/game_ids.py check`. `Combat.view()` / `Combat.from_view()` turn a
fight into plain data and back.
