# Randomized enemy HP for solvable end-game states? (2026-11-01)

The owner asked whether randomizing enemy HP would be a good way to make
end-game states the exact solver can solve. Four investigations (project
history, engine, distribution shift, prior art), a synthesis, and one
skeptic per key claim. Scripts and outputs are in the session scratchpad
(`hp-endgames/`), not committed.

## Verdict

**No as a label source.** Solvable low-HP states are almost all safe wins.
The states that would teach something are the ones the solver gives up on.
The useful role for the solver stays as a check (the 448 real puzzles at
horizon 1+), not as a source of labels.

## Evidence

- **Feasible without Rust.** Monster HP can be edited by rewriting the
  hp/max_hp varints in `Combat.encode()` bytes and decoding. This leaves the
  rules fingerprint unchanged (`solvedb/src/fingerprint.rs:18-27`). A
  `set_monster_hp` pymethod in `py/src/lib.rs` would be about 10 lines.
- **Naive edits make impossible states:**
  - a slime at or below half HP that hasn't split (`state.rs:950-953`);
  - a sleeping Lagavulin below max HP (`state.rs:946-949`);
  - a Guardian more than 30 HP down still in Offensive mode;
  - a damaged louse that still has Curl Up.

  Turn-1 states also lack Ritual strength, Enrage and status cards.
- **Solve cost has a cliff (one seed each, starter deck, bounds on, 1M
  nodes).** Below a per-encounter line a solve takes 2-15 nodes and the
  value is 2.0. Just above the line, the solver runs out of budget.

  | encounter | solves at | runs out at |
  |---|---|---|
  | Jaw Worm | 29-30 HP | 32 HP |
  | Gremlin Nob | 29 HP | 34 HP |
  | Slime Boss | 14 HP | 28 HP |

  Without bounds, none of the four low-HP cases solved.
- **Solved synthetic states carry almost no signal (100k nodes, bounds on).**
  - Turn-1 states with every enemy at 1-25% HP: 120 of 139 solve, all with
    value 2.0, and 87 of them end this turn.
  - Real turn-2+ states with enemy HP at 10-40%: 107 of 122 solve, 87% are
    safe wins and 1 is contested.
  - Neither the heuristic nor the champion picked wrong in either set. One
    turn or more from the end that is 0 of 33 and 0 of 20, which is weak
    evidence against the ~10% wrong-pick rate on real puzzles.
  - Caveat: the scoring took bounded options at their upper bound. A
    recheck on 39 states found every pick on a bounded option was still
    best.
- **The errors are elsewhere.** On the 448 real puzzles at horizon 1+, the
  champion with `@hpb0.01` picks wrong 10.3% of the time.
  - 81% of its regret is on elites.
  - 70% is on states whose exact value is 1-1.9, where the fight could
    still go either way.
  - Low enemy HP in a close race *is* an error zone: below 25% enemy HP,
    the champion picks wrong 16.9% of the time (n = 59, nearly all elites),
    which is 21% of its regret. But real games already contain those
    states. It's the safe-win slice, the one the solver handles easily,
    that has no errors.
  - When the player loses a tight fight, the enemy still has 61% of its HP
    on average.
- **HP pricing is an input gap, not a label gap.** In hallways the nets
  price HP at about 0.001 per HP, against the label's 0.01-0.02. The labels
  already price HP from the start of the fight; the net lacks a start-HP
  column. The start-HP arms (0059l5-l8) test the fix.
- **History.**
  - The exact-label work lowered regret but never raised held-out play:
    - 8x and 23x more exact labels;
    - frontier 2;
    - exact-only nets, which were worse players because they never saw
      early fights.
  - Dropping exact labels (the lean loop) cost at most ~0.02 on train.
  - Exact-label work is on the 2026-11-01 stop list.
  - lean-lowhp, which started 25% of games at 1-8 player HP, didn't help
    low-HP fights.
- **Prior art is mixed.** Reverse curricula and starts from demonstration
  states (Florensa 2017, Salimans & Chen 2018, Go-Explore) raise final
  performance where rewards are sparse. That isn't this project's problem,
  since every fight ends with an outcome.
  - What worked elsewhere was small changes to real states, kept a
    minority of the data: Giraffe, KataGo's 5% handicap games, Go-Exploit.
  - A value net on random states "fails to learn anything valuable"
    (ReBeL).
  - Tablebase rescoring in Stockfish training gave +3.8 Elo.

## If revisited

- **Cheap fallback for HP pricing.** Use it only if the start-HP arms don't
  raise the hallway HP price. Perturb player HP in real mid-fight states,
  holding start HP fixed, and use the simple shifted label. Don't use
  enemy HP for this.
- **Best-case test of the enemy-HP idea (under 5 core-minutes).**
  - Take real Lagavulin and Nob states 1-2 turns from the end.
  - Lower enemy HP by 10-40%, with max_hp = hp so the monsters stay legal.
  - Solve each at 100k nodes.
  - Pass if at least 20% of the states are solvable and contested *and* the
    champion picks wrong on at least 5% of them.
  - Today's data predicts about 1% contested, so a fail.
