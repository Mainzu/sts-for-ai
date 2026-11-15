# Pack chain: a pack of generated mechanics to its guarded net (lane pack-adapt-pipeline, step 1)

Status: closed (2026-11-08, built and in use; family.py queue on configs/packs; decisions "pack-adapt-pipeline step 1 built: the pack chain" and "Lane pack-adapt-pipeline closed": go).

**Outcome.** One command, `family.py queue configs/packs/<name>.json`,
queues the whole chain from a pack of generated enemy mechanics to the
pack's net and its table: the zero-shot bench read (if missing), one joint
burst per arm and seed, the bench read of each burst net, and a table job
that writes the per mechanic x parent cost cut, the retention rows and a
ship verdict; a net that passes the guard is written as the pack's net.

**How it moves goal 1, and how we'll know.** Goal 1 asks that new content
be supported, not only measured: a new mechanic should get a net that
plays it without costing the old content. Every part exists (the bench,
`gen-adapted-column`'s burst source, `family.py`'s session-free chain), but
today a session writes the burst configs, picks the base and reads the
retention rows by hand (`measurement/pack-joint-burst@gen-b1`). This step
makes the gate code; step 2 runs gen batch 1 through it with two arms (99
games per mechanic, with and without the three parents in the burst). We
know it works when the chain goes from the one queue command to a written
table with no session between, and the table's guard matches the hand read
of the pjb probe (it must refuse the pjb nets on TurnEnd-Frail x Lagavulin).

**Non-goals.** No engine or bench-play change; no new teacher or recipe
(retention terms are the navigator's question if no arm ships); packs of
generated cards; a product step (decision/burst-adapted-column: a pack's
net is named by the pack, not promoted).

## Behavior

A pack file (`configs/packs/<name>.json`) is a family file with a `pack`
key; `load_family` expands it in memory into an ordinary family, so
`queue`, `read`, `table` and `verdict` take the pack file as they take a
family file. Keys:

- `name`, `lane`, `parent` (the zero-shot net), `pack`: {`mechanics`:
  [`mutate_monsters.GEN` names], `encounters`: [parent elite encounters],
  `control` (ladder entry, default `c-hp1.25`), `starts` (1000), `seeds`
  (4), `base` (optional: an existing zero-shot bench file to pair with;
  default `results/packs/<name>/base.json`, queued), `burst`: {the burst
  config's settings: `net_settings` `@hpb0.01@tsl1`, `skip` 1000,
  `val_fights` 40, `game_seed` 71, `n_val` 300, `pool` 10000, `player`
  `net`; job `threads`, `mem_gb`, `estimate_min`}, `read`: {`threads`,
  `mem_gb`, `estimate_min`}, `arms`: {arm: {`games`: N, `parents`: bool}},
  `seeds_burst`: [1, 2], `guard`: {`hp` 2.0, `wins` 0.05, `min_se` 2.0},
  `target` (optional): {`mechanic`, `encounter`, `share`, `min_se`}}.
- **Burst configs** are written by `queue` (before anything is added) to
  `results/packs/<name>/<arm>-s<seed>.json` in main's data (snapshots reach
  `results/` through their junction), from the pack's keys: `mutated` is
  the mechanics, plus `"parent"` when the arm has `parents`; `games` is N
  (N fights per entry of `mutated` on the encounters). Rewriting an
  unchanged config leaves its bytes alone; a changed one is refused while a
  burst job of it exists (no silent change under a queued job).
- `mutate_monsters.ALL` gains `"parent": []` (no patch: the unmodified
  fight), so a burst can rehearse the parents; nothing else reads it.
- **Jobs:** the base read (`mutate_monsters.py play --players heuristic,one
  --net <parent> --mods <mechanics + ladder> --groups elite --starts S
  --seeds K --out <base>`) only when the base file is missing; each read
  (`--players one --net {net}@tsl1`, same starts, seeds and mods,
  `--out results/packs/<name>/read-{run}.json`) `--if-passed` its burst;
  the table `--after` the reads and the base job, with the verdict check.
  The base read is the bench's cost table: the table prints it.
- **Table kind `pack`** (`table_pack`), per net (paired by start with the
  base's first K seeds, on the pack's encounters):
  - per cell (each mechanic and `parent`) x encounter, and `parent` over
    all encounters: delta HP lost (net minus zero-shot) and delta wins,
    mean and se over starts; for mechanics the zero-shot cost (net minus
    heuristic beyond the control) and the cut (the burst's drop in that
    cost, `gen_cut`'s formula);
  - **guard:** a net fails when any cell loses `guard.hp` HP or more at
    `guard.min_se` se (delta >= hp and delta >= min_se x se) or `guard.wins`
    wins or more at `guard.min_se` se;
  - per arm: cells pooled over its nets per start, the target's cut against
    `target.share` x zero-shot cost at `target.min_se` se over nets (the
    lane's measure; reported, it does not gate shipping);
  - **ship:** among the nets that pass the guard, the one with the largest
    mean cut over the pack's mechanic x encounter cells; verdict `pass`
    when a net ships, `fail` otherwise. On pass, `results/packs/<name>.json`
    is written with the net, its arm, the table path and the time; on fail
    an earlier ship file is left alone and the table says it was not
    replaced. `verdict` exits 0 on pass.
  - writes `results/families/<name>.{md,json}` as the other kinds; the md
    holds the zero-shot cost table, the guard rows (every failing cell
    named) and per arm the cut and retention table.
- Missing reads (a failed burst, a short file under 200 starts) are listed
  and their nets left out, as `table_gen` does.

## Fits with

- Family files without `pack` load and queue as today
  (`test_queue_adds_the_chain_once` and the rest of `test_family.py`, unchanged).
- `table_gen`, `gen_cut` unchanged (`test_gen_table_*`).
- Burst source: `mutated_fights` and `mutated_games` treat `"parent"` as
  the empty patch; existing cache identities unchanged
  (`test_mutated_ident_unchanged`); new `test_mutated_parent_is_unpatched`.
- `mutate_monsters.play` with default mods is unchanged (`MODS` untouched).

**When in doubt:** prefer reusing `family.py`'s queue and `gen_cut`'s
pairing over a parallel driver.

## Scope

`scripts/family.py`, `scripts/analysis/mutate_monsters.py` (the `ALL`
entry only), `scripts/tests/test_family.py`, `scripts/tests/test_finetune_gen.py`,
new `configs/packs/`, README's family line if one exists, this spec. Off
limits: the engine, `finetune.py`'s training, `mutate_monsters.py`'s play
and read, existing family files and their tables.

## Decisions taken

- The pack file is a family file with a `pack` key, not a new script
  (one driver, the chain's existing conditions and skips).
- Burst configs live in main's `results/packs/<name>/`, written by `queue`,
  not committed: the pack file is the source, and a pinned snapshot still
  reads them through its `results/` junction.
- Guard per net (the shipped thing is one net), the lane's target per arm
  over nets (its existing rule).
- "Loses 2 HP at 2 se" read as delta >= 2 and delta >= 2 se (the pjb
  write-up's use: "rises past 2 HP at 2 se").

## Verification

- `test_pack_queues_the_chain`: a pack file with two arms x two seeds and
  no base queues one base read, four bursts (configs written with the
  right `mutated` and `games`, `parent` in the parents arm), four reads
  `--if-passed` their bursts, one table `--after` the reads and the base
  with the verdict check; queueing again adds nothing; with an existing
  base no base job.
- `test_pack_config_change_refused`: changing `games` after a burst is
  queued refuses and adds nothing.
- `test_pack_table_guard_and_ship`: synthetic base and reads: an arm whose
  nets cut the mechanic and keep the parents ships its best net
  (`results/packs/<name>.json` written); a net that loses 3 HP (se ~0.4) on
  one mechanic x encounter fails the guard and is named; a 1.5 HP loss
  passes; a 0.06 win drop at 2 se fails.
- `test_mutated_parent_is_unpatched`: `"parent"` in `mutated` plays the
  unmodified fight (no power added).
- End to end: `family.py queue configs/packs/gen-b1.json --dry-run` lists
  the chain; `family.py table` on a pack file pointing its arms at the
  pjb nets (`net` seeds) reproduces the probe's rows (TurnEnd-Frail x
  Lagavulin about +3.25, OppCard-Vulnerable x Sentries wins 0.765 to
  0.787) and refuses both nets.

## Don't guard

Hand-edited burst configs under `results/packs/`; packs mixing official
`MODS` with generated mechanics.

## Build steps

1. `"parent"` in `ALL`, its test. Check: `test_finetune_gen.py` passes.
2. Pack expansion and queue (configs written, base job, reads, table
   binding), tests 1-2. Check: `test_family.py` passes.
3. `table_pack` with guard, ship file and verdict, test 3; the end-to-end
   table on the pjb nets. Check: tests pass and the pjb rows match.
