# Adaptation curve on mutated monsters

Status: closed (2026-11-04, go, curve filled: decisions "Lane adaptation-curve closed (2026-11-04)"; kb measurement/adaptation-curve, measurement/adaptation-curve@1602).

## Outcome

Measure how many games a short fine-tune (the adaptation burst) needs
for the 10-29 net to stop paying the one-turn novelty cost of stage A's
unseen-power modifiers (SharpHide 2, its hp pair, Ritual 2), and whether it
keeps its strength on official content: the first point of goal 1's
"games to adapt" curve.

How it moves goal 1, and how we'll know: goal 1 is an AI that handles new
content; `docs/direction.md` names "few games to adapt" first under it.
Today the one-turn net loses 0.04-0.06 win rate on these modifiers beyond
what the heuristic loses (`measurement/mutated-monsters@stage-a`). If a
burst of ~1600 games halves that cost (2 se) with retention within 1.5 HP
on the one-turn cell gauntlet, the curve (400, 100 games next) is goal 1's
first games-to-adapt number. If it doesn't, the gap is in what the net can
see (the net half of `new-mechanics-workflow`), and if retention fails the
burst recipe is the wrong tool. Either way the read decides the lane.

Non-goals: two-turn reads, more training seeds than one (a lead), new
modifiers, packs (runtime-registry stage 3), any change to the product.

## Behaviour

- `scripts/finetune.py` takes a third kind of `content`: a dict
  `{"mutated": [<MODS names>]}` with optional `skip` (default 200: the
  read's fights, `mutate_monsters.py play --starts 200`, are never trained
  on) and `val_fights` (default 100). Fights are `bias_audit.fights` of
  `mutate_monsters.PRODUCT` (1471 elite and boss fights). Training games:
  fights `[skip, skip + games)` x every listed modifier, one game each
  (`games` is fights per modifier, so nested sizes share their first
  fights); validation: the last `val_fights` fights x every modifier.
  Each game starts at the fight's first decision with the patch applied
  (`mutate_monsters.mutate`) and its seed drawn from `game_seed`, the
  fight and the modifier; played by the parent net one turn deep
  (`<parent>@hpb0.01`, the `one` player's setting) in a Python loop of
  `sts.search_action` (limit `selfplay.LIMIT`), recording states.
  Labels: the final score, sampled as `selfplay.sample_states` does.
- Replay pool, Ironclad validation and vocabularies as for generated
  content: `varied` setups, an effects parent keeps its vocabularies (a
  non-effects parent raises). The encoded mutated sets are cached under
  `cache/` (rebuildable), keyed by content, sizes, seeds, parent sha256
  and layout; the registry run lists only the registry datasets it used.
- A modifier name not in `mutate_monsters.MODS` raises before any play;
  `skip + games` overlapping the validation fights raises.
- `mutate_monsters.py play --net <path>` plays the `one` player with
  `<path>@hpb0.01` instead of the 10-29 net, and records `net` in the
  file's settings.
- `mutate_monsters.py compare <base> <burst>`: per modifier in both files,
  paired by start on rows where both have the `one` player: the burst's
  gain in novelty cost `(one_b - one_a)(mod) - (one_b - one_a)(parent)`
  in win rate (mean, se), the base novelty cost (from base's heuristic and
  one rows), the share of the cost cut, and the parents' change
  `one_b - one_a` (official retention on these fights). The heuristic
  cancels: both files play the same seeds.

## The experiment

- Burst: `configs/adapt-sharp-s1.json`: parent the 10-29 net, content
  `{"mutated": ["sharp2", "sharp2-hp0.9", "ritual2"]}`, `games` 534
  (1602 games), `top` 534, `game_seed` 41, `seed` 1, `n_val` 300, `pool`
  10000, other keys at finetune's defaults (the burst8 recipe).
- Read 1 (novelty): `mutate_monsters.py play --starts 200 --seeds 8
  --players one --net <burst> --mods sharp2,sharp2-hp0.9,ritual2 --out
  results/adapt/burst534-s1.json`, then `compare results/mutate/a.json`
  it.
- Read 2 (retention): `gauntlet.py play <burst>@hpb0.01 --sequences 500
  --threads 3 --out results/gauntlet/adapt534-s1-hpb0.01.json` (no
  `--against`: fixed n), then `gauntlet.py read
  results/gauntlet/net1029-hpb0.01.json` it (`yardstick/one-turn-controls`).
- Rule (pre-registered, the charter's): **go** if the gain on sharp2 and
  on sharp2-hp0.9 each is at least half that modifier's base novelty cost
  and at least 2 se, and the paired HP difference on cells is above -1.5;
  then queue 100 and 400 games (`games` 100 / 400 configs, same game
  seed: nested). **Stop** if the gain fails (the net can't see it) or
  retention fails (wrong tool). Ritual 2's row is reported, not judged.

## Fits with

- `finetune.py`'s string kinds, generated-content dicts and `source`
  runs: their dataset configs unchanged (`test_finetune_gen.py`,
  `test_warm_start.py`, unchanged and passing).
- `mutate_monsters.py play` without `--net` and `read`: unchanged output
  (`test_mutate_monsters.py`, unchanged and passing).

## When in doubt

Prefer reusing `finetune.py`'s pieces and `mutate_monsters.py`'s patch
code over new machinery.

## Scope

May change: `scripts/finetune.py`, `scripts/analysis/mutate_monsters.py`,
their tests, a new `configs/adapt-*.json`, results docs, decisions.
Off limits: the Rust engine, `learn.py`, `selfplay.py`, feature layouts,
existing result files.

## Decisions taken

- Python loop for game recording (`sts.run` takes only specs; a patched
  start state isn't a spec): measured 0.1 s per fight on one thread, the
  same 13 of 20 wins as `sts.play_on` on the same states and seeds.
- The read's 200 fights are excluded from training; the comparison base
  is the stage A file (same starts and seeds), so no new base play.
- One-turn `@hpb0.01` player for the games: the setting whose cost we cut.

## Verification

1. `test_mutate_monsters.py::test_compare`: on two hand-made files, the
   gain, base cost and cut share come out as hand-computed.
2. `test_finetune_gen.py::test_mutated_unknown_mod`: an unknown modifier
   raises before play, naming it; an overlap of training and validation
   fights raises.
3. `test_finetune_gen.py::test_mutated_games`: 2 fights x 1 modifier
   recorded with the heuristic evaluator give 2 results whose states
   start with the patched monster (power present) and whose score equals
   the end state's.
4. End to end: a smoke burst (`games` 3, `val_fights` 2, `pool` 200,
   `n_val` 20) finishes and saves a model that `mutate_monsters.py play
   --net` accepts.

## Build steps

1. `--net` and `compare` in `mutate_monsters.py` (test 1).
2. Mutated content in `finetune.py` (tests 2-3), smoke (check 4).
3. **Long run:** queue the burst, then read 1 and read 2 after it.
