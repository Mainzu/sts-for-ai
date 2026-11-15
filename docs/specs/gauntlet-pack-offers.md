# Pack cards in the gauntlet's offers (act1-content block G1)

Status: closed (2026-11-07, built and in use; lane act1-content block G1; landed b2ff0d03; checkpoint cards-rerank passed, f17c2230).

## Outcome

`gauntlet.py play --pack <file>` offers a content pack's cards after each
won fight beside the official pool, so a run can draft and play pack
content, and the lane's headline re-rank for cards can run.

How it moves the goals and how we'll know. Goal 1 asks for first-class
custom content; today a pack card plays only in a single hand-made fight
(the zero-shot bench), never through the run layer's choices. Goal 2's
real Act 1 offers 75 Ironclad cards; the gauntlet offers 21 (train) and 31
(held-out). With the 27 Act 1 pack cards the pools become 48 and 58. Two
reads tell us: the product and the one-turn net, each `--against` its own
headline control `--vary pack`, give the effect of adding the cards (does
the chooser draft them well, does the fighter play them well), and the
order of heuristic, one-turn and product on the pack setting says whether
the product's lead (0.834 against 0.680 clears) holds on content it never
trained on.

Non-goals: pack monsters or encounters in the gauntlet (that is block E1);
rarity weights; pack cards in `--start cell` decks (they enter only by
offers); upgrading pack cards at a rest site beyond what `upgradable`
already does; Ironclad's real full pool (the official cards outside the
cells' pools stay out).

## Behavior

- `--pack <path>` loads the pack once in the main process
  (`selfplay.load_content`), and in every two-turn worker
  (`depth_paired.run_guarded(..., content=path)`, through
  `ladder.play_two_turn(..., content=...)`).
- The reward pools are `reward_pools(cells)` with the pack's base cards
  (ids not ending in `+`) added to both halves as `gen:<id>`, sorted with
  the rest. Offers stay uniform over the pool (`offer`, unchanged).
- `settings["pack"] = "<path>@<content hash>"`, absent without `--pack`
  (older files keep matching). `pack` joins `VARY` and `MATCH_FIELDS`
  (the pack decides what is offered, and a pack-less run can't replay
  `gen:` picks, so `--match` across pack settings is refused).
- `--pack` without `--rewards` other than `skip` is refused ("--pack needs
  --rewards": with no offers it changes nothing).
- A pack that fails to load stops the run with the loader's message.

## Fits with

- Without `--pack` every pool, offer, setting and result is identical:
  the existing `test_gauntlet.py` suite pins offers and settings; a new
  test checks `reward_pools(cells)` is unchanged when no pack is given.
- `--against` refuses a pack-less control unless `--vary pack`
  (`test_against_refuses_other_settings` pattern; new test).
- Upgrades: `upgrade(deck, "gen:X")` gives `gen:X+`, the pack's upgraded
  id; `upgradable` reads only official names, so a pack card is never
  offered for a rest upgrade (headline uses `--rest heal`; noted, not
  changed).
- The S1 slot limits (32 pack cards, 24 pack powers per fight) hold: a
  deck takes at most 10 cards from offers.

## When in doubt

Prefer leaving pack-less runs bit-identical over sharing code paths.

## Scope

May change: `scripts/gauntlet.py` (flag, pools, settings, play plumbing),
`scripts/ladder.py` (`play_two_turn`'s `content` pass-through),
`scripts/tests/test_gauntlet.py`, README's gauntlet section, the
inventory doc and decisions. Off limits: the engine, `py/src`, the pack
files, `depth_paired.py`'s behaviour, the control files.

## Decisions taken (provisional, in docs/decisions.md)

- Both halves get every pack card (alternatives: split the pack between
  halves as the cells are split; a pack-only pool). The pack is new to
  every net, so a half split teaches nothing, and a pack-only pool is
  further from the real game.
- Uniform offers (alternative: the game's rarity weights; the pools have
  none today).

## Outside assumptions

None: the pack, its loader and the workers' `content` argument are this
project's (the zero-shot bench played these 27 cards with the net).

## Verification

Tests first (`scripts/tests/test_gauntlet.py`):
- `test_pack_pools`: with the act1-ironclad pack, each half's pool is the
  old pool plus the 27 `gen:` base ids, sorted, no `+` entry; without a
  pack it equals `reward_pools(cells)`.
- `test_pack_settings`: `--pack` records `pack` as `<path>@<16 hex>`;
  without it the key is absent; `--pack` with `--rewards skip` exits;
  `--against` a pack-less control exits naming `pack`, and passes with
  `--vary pack`.
- `test_play_two_turn_content`: `ladder.play_two_turn(..., content=p)`
  hands `content=p` to `run_guarded` (monkeypatched).

End to end: `gauntlet.py play heuristic --start starter --rewards sim
--sim-boss --pack content/packs/act1-ironclad.json --sequences 6 --threads
3` finishes, at least one floor's `took` is a `gen:` card and a later
floor of that sequence played; and the product with `--two-turn
--line-seed --step-line --one-turn-floors 10 --pack ...` on 2 sequences
finishes (the boss floor plays two turns deep in workers that loaded the
pack).

Don't guard: rarity, pack monsters, `--start cell` decks with pack cards.

## Build steps

1. Tests, then the flag, pools, settings and `play_two_turn` pass-through
   (~40 lines). Check: the three tests and the whole `test_gauntlet.py`.
2. End-to-end runs above. Check: both finish, `gen:` picks seen.
3. Reads, queued (long runs): one-turn net `--pack` against
   `results/gauntlet/net1029-hpb0.01-starter-simboss.json --vary pack`
   (500 sequences, 3 threads); heuristic `--pack` against
   `results/gauntlet/heuristic-starter-simboss.json --vary pack` (500);
   the product `--two-turn --line-seed --step-line --pack` against the
   headline control `--vary pack`, 250 sequences at fixed n, 2 threads.
   Check: the job records; read per fight type and half, and which pack
   cards were taken, in the inventory doc.
