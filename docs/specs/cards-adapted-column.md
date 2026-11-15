# Cards adapted column (yardstick-cards step 3, second table)

Status: closed (2026-11-07, built and read, no burst closes a modifier's cost: decisions "After the cards adapted column"; kb measurement/cards-adapted@stage-a).

## How it moves goal 1, and how we'll know

Goal 1's number has two halves: what new content costs the net zero-shot,
and how few games repair it (decision/goal1-yardstick). The first card
table (measurement/mutated-cards@stage-a) found two modifiers whose cost
passes 2 se beyond the heuristic on the turn-start leaf: `inflame-turn1`
(-0.018 (0.005) wins with tsl, -0.043 (0.008) on the plain leaf) and
`metal-c2-a5` (-0.021 (0.006) on both leaves). This step measures the
second half on those two: a burst of about 400 games per group on decks
holding the variant (decision/burst-adapted-column), three training seeds,
read on the same starts and seeds as the zero-shot table. We'll know when
each modifier has a gain on its own row (burst minus zero-shot, wins and HP
lost, pooled over three seeds per start, se over starts) beside its
zero-shot cost, with the parent copy's and the official card's rows as
retention.

## Outcome

Six bursts (`configs/cadapt-<mod>-s<1|2|3>.json`) and six reads
(`results/mutate/cards-adapt-<mod>-s<k>.json`), then
`mutate_cards.py adapted` prints, per modifier and leaf (one, tsl) and by
fight type, the burst's gain on the variant, the parent copy and the
official card, and the zero-shot novelty cost beside it.

Non-goals: two-turn reads; cell-gauntlet or boss-replay retention (the
burst's decks are cards plus varied setups like step 2's; the parent and
official rows of the same fights are the retention read here); modifiers
whose cost did not pass 2 se; new engine atoms.

## Behavior

- **Pack file.** `mutate_cards.py pack --out data/bench/mutated_cards_pack.json`
  writes `pack()` (every modifier and copy); the file is committed so a
  pinned burst loads it. `play` always loads the full `pack()` (it loaded
  `pack(mods)` before; cards-a.json was played with every modifier, so the
  zero-shot rows were played with the same pack).
- **Bursts:** finetune's generated-content path: `content {"pack":
  "data/bench/mutated_cards_pack.json", "cards": [<mod>]}`, `player` net
  (the parent's own one-turn games), `games` 400, `n_val` 150, `pool`
  10000, one game set per modifier (`game_seed` 61 for inflame-turn1, 71
  for metal-c2-a5) and training seeds 1, 2, 3 (decisions "yardstick-cards
  step 2: one shared game set per arm and three training seeds"). The
  decks are varied Ironclad setups with 1-2 copies of the variant
  (`selfplay.content_deck`, share 1.0). The variants use only official
  powers (DemonForm, Metallicize), which the parent sees
  (how/burst-inputs).
- **Reads:** `play --net "runs/*-cadapt-<mod>-s<k>-*/model.pt" --mods <mod>
  --players one,tsl --starts 200 --seeds 16 --threads 3`. `--net` takes a
  glob; it must match exactly one file (else an error naming the matches).
  Starts and seeds are cards-a.json's (the first 200 fights holding the
  parent; seeds from the start).
- **adapted** `<zero-shot file> <burst files...>`: rows matched by (i,
  floor, card) with the zero-shot file; per start the bursts' outcomes are
  averaged over the burst files (three seeds pooled per start,
  yardstick/twin-reads), minus the zero-shot outcome; mean and se over
  starts, for wins and HP lost, on the variant row, the parent copy row and
  the official row; all fights, elites, bosses; the zero-shot novelty cost
  (net minus heuristic, from the zero-shot file) beside it; and each burst
  file's variant-row gain alone (the seed spread).
- **Prediction (trade-off rule), before the run.** What each leaf can gain:
  on the plain leaf `inflame-turn1` can regain up to its 0.043 cost;
  burst8's nets learned Demon Form's first tick only
  (measurement/burst8-tsl1@cells), which tsl already shows, so the burst
  should regain much of the plain-leaf cost and little of tsl's 0.018.
  `metal-c2-a5`'s block lands at the leaf's turn end, so its cost is in
  valuing a 2-cost play, not in a missed tick: the games can teach that
  on both leaves, and its gain should be alike on both. If both
  modifiers gain nothing on tsl, games at this size do not teach a rate
  past the first tick (the cards rung's adapted column is zero there).
- **Read rule.** A modifier is repaired on a leaf when its variant-row gain
  is at least 2 se and its parent-copy row keeps within 2 se of zero
  (or gains); the repair fraction is the gain over the zero-shot cost
  (the net's change from the parent minus the heuristic's, sign flipped).

## Fits with

- `mutate_cards.py play`/`read`: unchanged output format;
  `scripts/tests/test_mutate_cards.py` still passes.
- `finetune.py`: unchanged; the generated-content path as burst8 used it.

## Scope

May change: `scripts/analysis/mutate_cards.py`,
`scripts/tests/test_mutate_cards.py`, `data/bench/mutated_cards_pack.json`
(new), `configs/cadapt-*.json` (new), this spec,
`docs/research/learned-play-results.md`, `docs/decisions.md`, this lane's kb
facts. Off limits: the engine, `py/`, `finetune.py`, `family.py`, content files.

## Verification

Tests first (`scripts/tests/test_mutate_cards.py`):
- `test_pack_file`: the committed pack file equals `pack()`.
- `test_net_glob`: one match resolves; none or two raise.
- `test_adapted`: on hand-made zero-shot and two burst files, the gains on
  the variant, parent and official rows equal hand-computed pooled means.
- `test_burst_configs`: each `configs/cadapt-*.json` names a card of the
  pack file, and `finetune.generated` accepts its content.
End to end: the six bursts and reads in the queue (the long run).

## Build steps

1. Code and tests in-session; `test_mutate_cards.py` and
   `test_mutate_monsters.py` pass.
2. Queue six bursts (`finetune.py --from <product net> --config
   configs/cadapt-<mod>-s<k>.json --threads 4`, 2.5 GB, 30 min), each read
   `--if-passed` its burst (3 threads, 1.5 GB, about 8 min: 200 starts x 16
   seeds x 3 decks x 2 players), and one `adapted` job `--after` the six
   reads (its log is the table; the lane copies it into the results doc).
