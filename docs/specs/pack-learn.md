# Pack learn: from-scratch learns on content packs

Status: closed (2026-11-09, built and in use; 33e159d3; learn.py packs key; decisions "pack-net-scratch: pack learn design" and "Lane pack-net-scratch closed": go).

Lane `pack-net-scratch` step 1 (charter `lane/pack-net-scratch`). Confirmed
under the mandate (on the owner's behalf, 2026-11-09).

## Outcome

`learn.py` takes a config key `packs` (a list of content pack files) and
plays every self-play game, training and validation, on all content: the
pack's cards join the all-content deck pool and its encounters join their
groups. A from-scratch net can then learn on the Act 1 pack.

How it moves goal 2, and how we'll know: the pack drop on the headline
(`measurement/act1-cards@pack-offers`: one-turn net -0.158 clears) is in
fighting the new cards (`measurement/pack-pick-split@headline`), and new
content is the one training input the owner's training rule allows. Seed 1
read one turn deep `--against` the one-turn pack control on sequences 0-499
says whether a net trained on the pack fights it better (charter's stop
rule: 2 se on the pack setting, retention within 1.5 HP on the cell
gauntlet). For goal 1 it is the from-scratch end of the pack-net question
(how much does a net gain from training on new content at all).

Non-goals: two-turn search, the solve step on pack content (pack states
have no codec bytes, so they get no exact labels; `solve_games` stays 0),
packs outside the all-content pool, the gauntlet's own pack handling.

## Behavior

- `packs: [path, ...]` needs `setups: varied` and `deck_pool: all`; with
  either missing `learn.dataset` raises ValueError.
- Each pack is loaded in-process (`selfplay.load_content`); the dataset
  config gets `packs: [content hash, ...]` in the config's order.
- Decks: `full_pool_deck`'s draw, over the official Ironclad pool (held-out
  cards included) plus every card of every pack (`gen:<id>`, upgrades
  included), uniform.
- Encounters: for each group, a pack's encounters of that group join it.
  On a stream of its own (seeded from the spec seed), each spec of that
  group takes an added pack encounter with probability added / (added +
  official in the group), else keeps its official draw, or that draw's pack
  version when a pack encounter's id names it (`Exordium Thugs` ->
  `exordium_thugs`), as the gauntlet's `pack_hard` does. Decks, HP and
  combat seeds are unchanged by the swap. The swap runs after `bosses`.
- The dataset manifest records `content_hashes` and stores each pack
  (`registry.store_pack`); encoding a dataset loads them first
  (`registry.ensure_content`), as it does `content_hash` today.
- The run's round record gets `content_hashes`.
- Without `packs` every dataset config, deck and spec is today's.

## Fits with

- Configs without `packs`: dataset configs unchanged
  (`test_all_content_keys_enter_dataset_config`, and the new test below
  checks the config has no `packs` key).
- `content` (generated powers, train split): untouched; both may be set.
- `with_bosses`: runs first; boss swap unchanged
  (`test_bosses_swap_boss_group_encounters`).
- Encoding: a dataset without `content_hashes` encodes as before.

When in doubt: prefer the gauntlet's pack conventions over new ones.

## Scope

`scripts/learn.py`, `scripts/selfplay.py`, `scripts/registry.py`,
`scripts/tests/test_setups.py`, a new config `configs/packnet40k-s1.json`,
this spec. Off limits: the engine, `gauntlet.py`, existing configs.

## Verification

- `test_pack_keys_enter_dataset_config`: `packs` puts two hashes in train
  and val configs; without `deck_pool: all` it raises.
- `test_pack_pool_deck_draws_pack_cards`: over 300 decks, extra cards hold
  pack cards and official held-out cards; sizes 13-25.
- `test_with_pack_encounters`: hallway specs take added pack encounters at
  about the expected share (3 added of 11 official: 0.21, 2000 specs, within
  0.04), `exordium_thugs` turns into `gen:Exordium Thugs`, elite and boss
  specs unchanged, decks and seeds unchanged.
- End to end `test_pack_dataset_plays_pack_content`: a tiny round-0 dataset
  with both Act 1 packs holds a `gen:` card in some deck and a `gen:`
  hallway encounter, its manifest names both hashes, and it encodes.

## Build steps

1. Tests above, then the code; `test_setups.py` passes. (in-session)
2. `configs/packnet40k-s1.json`: `allcontent40k-s1` plus both Act 1 packs;
   queue the learn (long run, about 3.5 h at 6 threads; `mem_gb` from
   commit, 2 GB) and the one-turn pack control at the same pin.
