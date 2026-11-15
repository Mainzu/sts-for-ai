# Finish-faster tie break: replay read (2026-11-09)

Lane `finish-faster-tiebreak`, step 2 (spec
`docs/specs/finish-faster-tiebreak.md`). The product
(`runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt@hpe0.01`, two turns,
line seed, line step) replays headline control sequences 0-29, every floor
(330 fights), from
`results/gauntlet/net1029-hpe0.01-two-line-step-starter-simboss-a.json`,
with the tie break off (job 0680, `results/depth_probe/tiebreak-off.json`)
and on (`@tb1`, job 0681, `results/depth_probe/tiebreak-on.json`). Read:
`depth_probe.py read results/depth_probe/tiebreak-off.json results/depth_probe/tiebreak-on.json`.

## Result

The off arm reproduces all 330 control fights (won and end HP), so the
replay is the product.

| Fight type | Fights | Nodes off | Nodes on | Nodes cut | Turns off | Turns on |
|---|---|---|---|---|---|---|
| easy | 90 | 1,183,271 | 1,174,527 | 0.74% | 315 | 303 |
| hard | 150 | 42,373,231 | 42,384,343 | -0.03% | 594 | 570 |
| elite | 60 | 13,532,443 | 13,532,538 | 0.00% | 341 | 337 |
| boss | 30 | 35,068,543 | 35,068,549 | 0.00% | 263 | 263 |
| all | 330 | 92,157,488 | 92,159,957 | -0.003% | 1,513 | 1,473 |

End HP and wins are identical in every one of the 330 fights. 48 fights
change: 41 end one turn sooner and 1 a turn later (40 turns saved, 2.6%),
6 only reorder their play; all keep their end HP.

**Stop rule: fail.** Step 2 cuts under 3% of the search nodes (it cuts
none), so step 3's 250-sequence read doesn't run.

## Why

- The turns it saves cost almost nothing. In a changed fight the off line
  wins one turn later at the same HP (the extra turn costs no HP, or
  Burning Blood's heal caps both at max HP), so both wins score exactly the same; the extra turn is
  one small search over a nearly dead fight. Typical: cultist (2, 2) 3,883
  -> 3,503 nodes, jaw worm (27, 1) 7,635 -> 5,439; the largest saving is
  two_fungi_beasts (8, 7), 5,634 nodes.
- The cost is elsewhere. Easy floors hold 1.3% of the gauntlet's nodes;
  hard hallways, elites and bosses hold 98.7%, and there the top options
  almost never tie exactly (HP loss separates them). Over 234 two-turn
  starter decisions, 90 had tied top values, but only 1 changed its pick:
  most tied options also tie on both keys (the same win turn, enemy HP 0).
- A few fights search more with it on (looter (17, 9) +5,506, thugs
  (29, 7) +16,704): a different but equal line reaches different states.
  These cancel the easy-floor saving.
- The owner's sequence-22 picture holds (many exact ties in easy fights),
  but the backlog's against-case was right: the ties are mostly
  transpositions or same-turn wins the keys can't separate, and the cost
  of a two-turn read is not in easy fights' last turns.

## What it changes

- Machine time: no gain from exact-tie breaks. The option stays in the
  engine, off by default (`@tb1`), harmless and identical off.
- The 30% wall-time saving of playing floors 1-3 one turn deep
  (`measurement/mixed-depth@headline`) comes from the searches of every
  turn of those fights, not from their length; cutting the length by tie
  breaks can't reach it.
- CPU used: about 1.0 cpu-h of the 7 cpu-h cap (two 3-thread jobs of
  9-10 minutes, plus local checks).
