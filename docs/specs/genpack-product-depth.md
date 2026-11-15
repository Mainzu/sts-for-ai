# genpack-product-depth: the generated-pack recipe read two turns deep

Status: closed (2026-11-12, read: between, two-turn pooled cut 0.60 (0.20); decisions "Lane genpack-product-depth closed (2026-11-12)").

Lane `lane/genpack-product-depth` (charter: decisions "Lane
genpack-product-depth opened (on the owner's behalf, 2026-11-11)").

**Outcome.** The mutated-monster bench gains a `product` player (two turns
deep with the product's flags: line seed and stepped line), and the lane
reads, on the 6 old held-out generated rows, the product's own novelty cost
and the generated-pack nets' cut against it at that depth.

**Goals.** Goal 1: every transfer of the generated-pack recipe on record is
one turn deep (cut 0.76 on unseen enemy pairings,
`measurement/genpack-transfer@three-seeds`); the product plays two turns
deep, where the second turn already repairs part of in-horizon novelty
(`cause/leaf-gain-third`). If the product's own held-out cost is under 1 HP,
the second turn already prices these mechanics and the recipe has nothing to
add where the product plays (fail-fast); otherwise the pooled cut over three
seeds says whether the recipe still pays at product depth, the baseline every
later goal-1 change at that depth needs. We know from the read: base cost,
cut and its se, parents' HP.

Non-goals: new content, training, the random-world bench (see Decisions).

## Behavior

- `mutate_monsters.py play --players ...,product`: the `product` player is
  `--two-net` (default the 10-29 net) `@hpe0.01` played by
  `depth_paired.run_guarded` with `seed_per_turn` and `step_line` (as
  `gauntlet.py --two-turn --line-seed --step-line` plays it), on the same
  starts, seeds and variants as the other players. `--two-starts` and
  `--two-seeds` apply to it as to `two`. All its fights go to one process
  pool after the per-start loop; each finished fight is appended to
  `<out>.partial` (progress: its lines of the total the job prints), a rerun
  plays only the rest, and the partial file is deleted once the rows are
  written.
- A start reaches a worker as `{state: hex bytes after the official patches,
  seed, powers: [[slot, power, n]]}` (`variant_parts`); generated
  combats have no state encoding, so pack powers are added in the worker
  after decoding (`depth_paired.start_combat`), whose pool loads the
  generated and fickle packs as JSON texts.
- `genpack_cut.py --player product --pair <product file> <genpack file>
  [...]`: costs of the `product` player; the 10-29 bar is the base files
  themselves; prints the parents' HP lost (genpack minus base) and the stop
  rule's line; `--gate` exits 1 when the fail-fast fires (base held-out
  pooled cost under 1.0 HP).

**Fits with:** `play_variants` and the `one`/`two` players unchanged
(`test_bench_bytes_path_identical`); `variant()` plays as before
(`test_start_combat_matches_variant` pins the state path against it);
`run_guarded` from deck specs unchanged (gauntlet two-turn, two_turn_games);
`genpack_cut` default player `one` unchanged (`test_wide_cut`).

**When in doubt:** prefer more distinct starts over more seeds per start.

**Scope:** `scripts/analysis/mutate_monsters.py`, `depth_paired.py`,
`genpack_cut.py`, their tests, this spec, the results doc
(`docs/research/generated-enemies.md`). Off limits: the engine, the gauntlet.

## Decisions

- **200 elite starts x 2 seeds, not x 4** (on the owner's behalf): a smoke
  ran 14 stepped two-turn fights in about 60 s on one thread (about 15 a
  thread-minute); 200 x 7 variants x 4 seeds is 5,600 fights a player, about
  6 thread-h each and 12 for step 1 alone against the lane's 18-cpu-h cap.
  Halving seeds keeps every start (start-to-start variance is the larger
  part, and starts pair across files). The heuristic reference plays the same
  2 seeds. Alternatives: 100 starts x 4 (fewer distinct starts, same cost);
  keep x 4 and drop step 2 (no seed spread, which the go rule needs).
- **The random-world rows wait** (descriptive in the charter): they run only
  if the cap leaves room after step 2 (about 6 thread-h at the charter's
  estimate, more at this pace).

## Verification

- `test_start_combat_matches_variant`: a (state, seed, powers) start plays
  exactly as `variant(c, mods).with_seed(seed)` (heuristic, official and pack
  mods). `test_guarded_fight_from_pack_start`: a stepped two-turn fight runs
  from a pack-power start in a worker that loads the pack, twice the same.
  `test_product_player` (genpack_cut): known costs read back, the fail-fast
  and `--gate`.
- End to end: a 1-start smoke of `--players heuristic,product` on the 6 held
  rows wrote both players' rows (done before queueing).

## Build steps

1. Product player and the cut's `--player` (this commit); check: the tests
   above pass.
2. **Long run** (queued): step 1, `results/mutate/gpd-product.json` (10-29
   net) and `gpd-gp1.json` (generated-pack seed-1 net), `--starts 298
   --groups elite` (the first 200 elite starts) `--seeds 2 --two-seeds 2`;
   read `genpack_cut.py --player product --gate`: fail-fast closes the lane.
3. **Long run** (queued behind the read's check): seeds 101 and 201
   (`gpd-gp101.json`, `gpd-gp201.json`), then the pooled read over three
   pairs: go if cut 0.4+ at 2 se with parents within -1.5 HP; fail if under
   0.2 or not 2 se.
