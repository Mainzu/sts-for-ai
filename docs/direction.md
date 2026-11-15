# Direction (the owner's file)

Written only from a reviewed discussion with the owner (`/approach`); it
outranks every other ranking; the navigator reads it on its next run.

## Goal weights

Development weight (what gets specced and built):
- Goal 1, plays well on generated content (few games to adapt; first-class
  custom content): 0.8
- Goal 2, a dominant StS AI (the headline gauntlet, `yardstick/headline-setting`): 0.2

CPU weight (what the machine runs):
- Goal 1: 0.6
- Goal 2: 0.4

## Interests

- Act 1 implementable in the engine through the runtime registry
  (`decision/registry-first`): every card, power, monster and relic of the
  real Act 1 as content files, not code (the missing Ironclad cards and
  Act 1 monsters, relics, potions, events, shops, gold, the map).
  Decision-making on it comes later.
- Resources that carry across fights (potions, max HP, relic counters;
  gold isn't built yet) are in the engine but off or unpriced in every fight played or
  measured, until a run can price carrying them: a per-fight score always
  spends them at once.
- Content is checked against the real game's own code: the installed
  desktop-1.0.jar read with javap first, decompiled copies where bytecode
  is hard to read; sts_lightspeed and the wiki are leads only
  (`decision/parity-source`).
- Goal 1's standing number on the owner's yardstick
  (`decision/goal1-yardstick`): boon + bane modifier pairs on official
  parents, measured per modifier; new mechanics, not new cards, are what
  hurts.
- Search and depth: gauntlet gains come from search and the run layer.
- Making runs cheaper (machine time is the bottleneck).
- Cheap probes of new approaches and combinations.

## Search depth in experiments

- Every comparison plays one turn deep (`@hpb0.01`, the one-turn
  controls), unless the question is about search depth itself or needs
  it (`decision/one-turn-comparisons`).
- The product (two turns deep) is the best setting we produce and the
  reported headline score: an augment on top, not the ruler a change is
  judged on.

## Level and more general is a pass

- A change that fixes a misprice, reads the game as it shows itself, or
  holds across content today's fights don't vary (max HP, characters,
  modified cards) is adopted on a level-or-better read, not on the
  protocol's +1.5 HP: end HP not below -1 HP at 2 se and clears not
  below -0.02 against the control, with no goal-1 row worse by 1 HP or
  more at 2 se. The protocol's early fail on such a change says nothing
  about "worse".
- A closure that rested on the protocol's fail alone, for a change of
  this kind, is re-read under this rule before its reason stands.

## Exact before sampling

- An evaluation over chance (a draw, a roll) averages exactly over every
  possible outcome; a sampled count of seeds is used only where exact is
  genuinely not feasible, never as the first solution, and the spec says
  why.

## Avoid

- Run-level decision work (card picks, rest, elites, path, potion use)
  before the content it chooses between is in the engine.
- Training that has nothing new to learn (the owner's training rule in
  `docs/operating.md`).
- Promoting nets by proxies (ladder, tight2) instead of the headline.
- Specs that can't say how they move goal 1 or goal 2.
- Anything the standing grants don't cover.
