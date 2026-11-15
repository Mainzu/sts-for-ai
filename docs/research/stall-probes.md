# Stall probes: leaf-beats-win (backlog 82) and stalls (backlog 85)

Lane final-round step 2. Replays the real-game decisions (`results/real-game/*/decisions.jsonl`) through the product's two-turn search (`scripts/analysis/stall_probe.py`: `Combat.from_view`, `depth_paired.decide`, the bridge's own call). The plain pick matched the recorded pick in every strict case, so the replay is faithful.

## 82: the win cap (`@wc1`)

`py/src/lib.rs` `add_prices`: an unfinished leaf's net value is capped at the score of a win at the HP it can still reach (HP + the win heal, at most max HP), less 0.001. Without the margin the capped leaf ties the win and the tie goes to the lower option index, which often is not the kill.

A decision is a case when a first action that wins at once exists and the plain search's pick is not that one. "Kills" counts the cases whose planned line (the bridge's play) ends the fight inside the turn; a pick that is not a win itself can still play on to the kill (Defend+, then Rampage).

| Source | Cases | Plain kills | `@wc1` kills |
|---|---|---|---|
| Run 56 floor 14 (Blue Slaver at 6 HP) | 10 | 1 | 9 |
| Run 52 floor 5 (gremlins) | 4 | 0 | 3 |
| A0 records 060511, 062806, 080956 (bosses and floors) | 13 | 7 | 8 |
| 145619 floor 7 | 2 | 1 | 1 |

No case where plain killed and `@wc1` stopped. Stall mechanism seen directly (run 56 turn 11): carrying on (Defend+) scored 1.363 against the kill's 1.232; with the cap every line that wins inside the turn scores 1.232 and the plain tie-break to the lower index no longer rewards the unfinished one. Cases left open: run 52 turn 12, run 56 turns 9-12 and 14, 145619 turn 1 (no kill inside the turn in either arm; the kill there is a later-turn line). Verdict: pass the probe; the adoption read (decision/level-pass) follows. Caveat unchanged: the cap ignores HP a leaf's own lines can still gain (Reaper, Feed).

## 85: progress term (killed)

Tried in the tree (search.rs): a leaf where no monster lost HP or died since the root scores c lower. Run 83 floor 5 (record 20261114-205554): turn 6 plain already kills the Shield Gremlin (slot 1); turn 20 `@pg0.03` and `@pg0.05` switch from striking the block to the kill; turn 40 stays on slot 2 at every c from 0.03 to 0.3 (two Strikes at 11 block count as progress: 12 damage). The probe's kill-fast rule applies (it still strikes the block): the fix needs the net input (backlog 81's), and the term is not built into the tree. Code removed.

## Turn cap in self-play

`scripts/selfplay.py` `hp_label`: a game that is not won, which includes one stopped at `PLAY_TURN_LIMIT` (100 turns; `runner.rs` stops it lost, `stalled` true), is labelled `HP_CAP`, as a loss. A stall is not labelled like a fight still going. Nothing to change.

## Pre-existing failure noted

`cargo test -p sts-py --lib`: `features::tests::card_vectors_pinned` fails on main since Row 1 (805065dc, `next_draw` inputs); not from this change.
