# Do the nets need enemy identity or move patterns? (2026-10-30)

The owner asked to move enemy attack patterns (umbrella spec 9) up, since
the nets seemed forced to be generic over all Act-1 enemies. Five
investigations (features, per-encounter results, value error, design,
prior art), then a synthesis, then two skeptics per key claim. Scripts:
`scripts/analysis/pattern_*.py` (single-threaded, read-only; outputs in
`scripts/analysis/out/`, not committed).

## What the nets see

- Per monster: alive, hp, max_hp, block, can_split, escaped,
  intent_damage, powers (effects mode: the 6 modifiers as columns, hook
  powers as rows; ModeShift dropped) and the **current intent's effects**
  (`py/src/features.rs` 220, 457-462, 780-797). No kind column, no
  previous move (`moves[1]`), nothing about later moves, no phase or
  counter. The heuristic, by contrast, runs the engine's own AI over the
  next 4 moves (`heuristic.rs` `damage_rate`).
- **Kind is still visible as a fingerprint.** Over 14,412 random-play
  states (17 encounters x 40 seeds), max HP, powers and intent tell every
  kind apart except Red / Green Louse (21% / 30% of their states) and the
  large slimes on Split (5%). That shows the kind *could* be read, not
  that nets read it (`pattern_identify.py`).
- **Unrolled intents at the leaves (new).** At one-turn End-turn leaves,
  a monster with a random AI hasn't rolled its next move: it still shows
  the move it just used, with one state-wide `pending_monster_move` flag.
  Share of leaves: Jaw Worm and Acid Slime M 100%, Acid Slime L ~94%,
  lice, Nob and Spike Slime M ~78-82%. Deterministic AIs (Sentries,
  Lagavulin, Slime Boss, Hexaghost, Guardian) roll inside EndTurn, so
  their leaves are right. Training afterstates are built the same way, so
  training and play match; the information is missing in both.

## Does it cost play?

- **On training cards, no sign of it.** The nets lead the heuristic most
  on the patterned encounters: Slime Boss +0.137 (se 0.017), Lagavulin
  +0.108 (0.022), Nob +0.053 (0.013); pattern-light hallway fights sit
  near 0 (`pattern_by_encounter.py`, 19 nets, cell-clustered se; groups
  of nets agree r = 0.93 across encounters).
- **Value error before big hidden hits: none.** On real outcomes (8,565
  states, 3,400 games neither net trained on), the champion's bias before
  a 6+ damage jump vs before a similar move differs by +0.007 (se 0.014);
  slope -0.010 per 10 damage (se 0.005). Slime Boss on Preparing, before
  Slam: -0.070 (se 0.033, n 380), slightly *pessimistic*; a blind net
  would be +0.1 to +0.35 optimistic (`pattern_value_error.py`). Exact
  labels cover hallway fights only and agree (-0.008, se 0.018).
- **On held-out cards and unseen bosses, maybe.** The patterned elites
  and bosses lose their lead: Lagavulin +0.005 (0.023), Sentries -0.008
  (0.022), Hexaghost -0.042 (0.039), Guardian -0.131 (0.032); Slime Boss
  keeps +0.073 (0.027) and Nob +0.040. The train-to-held-out drop goes
  with pattern score (Spearman +0.72, 15 encounters), but elite/boss
  status (+0.66) and the size of the train lead (+0.67) explain it as
  well; Nob is the only elite control. Unseen cards meeting Metallicize,
  Artifact or Dazed would give the same picture.
- **Depth with net leaves, the one direct test, is weak.** Two-turn search
  plays the real next move; on Lagavulin, Sentries and Slime Boss it
  helped net leaves more than heuristic leaves by +0.046 (se 0.027) train
  and +0.064 (0.027) held-out (one net, biased 50k cap). Held-out
  Lagavulin alone +0.170 (0.052), train Lagavulin +0.030 (0.061). (The
  synthesis first quoted +0.13 / +0.11; skeptics showed those are the
  contrast against Nob, whose own value is negative.)
- The nets trail the heuristic on training cards only in mixed hallway
  fights (thugs -0.016, wildlife -0.010), concentrated in Cultist
  pairings, where the next move is fully predictable from the intent.
  Kill order against Ritual is the likelier cause.

## Verdict

The owner is partly right. Nets get no identity and no future moves, but
on the 15 trained encounters they evidently learn each enemy from its
fingerprint; the value net isn't fooled before big hits and the nets
beat the pattern-aware heuristic hardest on patterned enemies. The real
gaps are (1) unseen monsters and unseen cards, goal 1's case, and (2)
stale intents at End-turn leaves for random-AI monsters.

## Options

- **(a) Kind one-hot columns.** ~100 lines, adds little for Act 1 (kind is
  already readable), nothing for goal 1: unseen monsters land in an
  untrained `kind_unknown` slot, and the net may lean on ids instead of
  effects. Prior art: identity-grounded baselines collapse on unseen
  content (EMMA's 18 vs 85); if ids are ever wanted, train with identity
  dropout (DropoutNet) and check held-out bosses.
- **(b) Lookahead columns (recommended).** Per monster, the expected
  effects of the next 1 and 2 moves plus the heuristic's 4-move damage and
  hit rate, from the engine's existing `move_distribution` rolled forward
  the way `damage_rate` does. At a paused leaf, next1 is the pending
  roll's distribution, which closes gap (2). ~150-250 lines in `agent.rs`
  (or the py crate) and `features.rs`, outside the 8 fingerprinted rule
  files, so golden games, fingerprint and solved DB stay; old nets drop
  the columns through the gather; feature pins get re-pinned. Works for
  any monster with a move distribution, so for generated monsters too;
  spec 9 later only changes where the distribution comes from, and Runic
  Dome needs this same input. Prior art: KataGo learned ~1.55x faster
  with search-computed tactical inputs.
- **(c) Full spec 9 now.** 800-1,500 lines, flips the fingerprint
  (monsters.rs is hashed), and hands a pooled MLP a program to interpret;
  the RTFM/EMMA line suggests reading rows directly needs attention.
  Stays the long-term source of the numbers in (b).

## Experiment for (b)

Arms: lean-thr (threshold-rows step 5's 3 nets) vs lean-thr+look, same
config and seeds, same round-0 data re-encoded. Judged paired on tight2
by half and fight type, tight_bosses per boss (Hexaghost and Guardian
zero-shot), and in advance on held-out Lagavulin, Sentries and Guardian;
rerun `pattern_value_error.py` on the best B net; one ladder test. MDE
with 3 seeds per arm: overall ~0.015, hallway ~0.010, elite ~0.043, boss
~0.05, per boss ~0.06. Cost ~15-17 CPU thread-hours (~1.5 h on both heavy
slots). Adopt as default if held-out elite+boss gains >= 0.045 or
held-out Guardian >= 0.06 with train no worse than -0.015; inside the MDE
everywhere: keep it behind a flag (spec 9 and Runic Dome want it) and
record that patterns aren't the Act-1 bottleneck.

Risks: a null is weak evidence at these MDEs; the held-out loss may be
card interactions, not patterns; the monster path grows from ~62 to ~160
columns; expected values blur either/or moves (Looter's Lunge or Smoke
Bomb); the encoder must stay within the contract's 5-10% budget.
