# Pack offers without pack picks (lane pack-pick-split, step 1)

Status: closed (2026-11-08, read failed: the pack drop is dilution; decisions "Lane pack-pick-split closed"; --pack-picks kept in gauntlet.py).

## Outcome

`gauntlet.py play --pack <file> --pack-picks originals` offers the pack's
cards exactly as `--pack` does, but every chooser may take only an
original (non-pack) card from an offer, or skip. With it, a read splits
the Act 1 pack-offers drop (`measurement/act1-cards@pack-offers`: 0.106
to 0.158 clears) into dilution (fewer original cards offered) and choice
(the chooser takes pack cards that cost it, `cause/chooser-horizon`).

How it moves goal 2 and how we'll know: the one-turn net @hpb0.01 and the
heuristic on the headline setting with the pack and the flag, sequences
0-499, each read against its pack file and its plain control. If either
recovers half or more of its drop at 2 se, the chooser's error is a goal-2
target worth about 0.07 clears (the parked chooser work reopens); if both
recover under a quarter, the drop is dilution and the pack read stands as
the harder headline.

Non-goals: a better chooser; changing what is offered; rest upgrades.

## Behavior

- `--pack-picks {any,originals}`, default `any` (today). `originals`
  needs `--pack` and `--rewards` other than `skip`, else refused.
- Under `originals`, `settings["pack_picks"] = "originals"` (absent at the
  default, so older files keep matching); `pack_picks` joins `VARY` and
  `MATCH_FIELDS`.
- Offers are unchanged (same pool, same draw). The chooser (any kind:
  random, sim, vrun, value; card and elite extra offers) scores and
  chooses among skip and the offer's cards that are not the pack's
  `gen:<id>` base cards; an offer of only pack cards is skipped. The
  floor row records the full offer and the pick; the explorer's
  `options` list only what the chooser could take.

## Fits with

- Default runs are bit-identical (the existing suite pins them).
- A test: under `originals` no pick is a pack card while offers hold them.
