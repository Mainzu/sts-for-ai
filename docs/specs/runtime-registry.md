# Runtime registry (rules-engine spec 10)

Status: closed (2026-11-06, built and in use; stages 1-4 built and landed; stage 5 moved to docs/specs/sparse-state.md; decisions 'Lane runtime-registry closed (2026-11-06)').

Umbrella: `docs/specs/rules-engine-upgrade.md` (series row 10, "Runtime
registry", "State representation for open-ended content", "Content in the
versions"). Drafted 2026-11-02 by the overnight series session after
specs 2, 4-9 were built; **left for the owner** because it reopens the
"static Rust tables" decision and the state representation, both
expensive to reverse, and because it is where the big-picture reviews'
re-scope (`docs/research/big-picture-2026-11-01.md` rank 8: widen
registry-lite to generated attacks, skills, a character and monster
patterns; retrain after each step) meets the series.

## Outcome

Content (cards, powers, monsters) can come from data files at runtime,
using every atom the series built, so generated content is first-class
(goal 1) and new official content needs no engine edit; the versions
(rules fingerprint, the registry's rules version) see the loaded content.

## What exists after specs 2-9

- Registry-lite: generated powers and *power cards* from a JSON pack,
  bound per combat to 8 power and 8 card slots; the codec refuses states
  holding them.
- Every atom is data inside the engine: amount expressions, tags, X-cost,
  statics, replacements, `OwnerAttacked` / `RoundEnd` / `OwnerPlaysCard`,
  picks, replay, the known top, variants, monster patterns.
- State: fixed arrays sized by compile-time tables (piles 152 card slots,
  27 official powers + 8 generated); state 1,268 bytes (1,028 before the
  series), and about 75% of a two-turn search copies and hashes states
  (decisions "Series speed and search identity after specs 2-9").

## Proposed stages (each built and checked alone)

1. **Pack covers every atom** (the re-scope's first step): the pack parser
   and a serialiser accept every `Effect`, `Trigger`, `Condition`, static,
   replacement and pick the engine has; generated *attacks and skills*
   (not only power cards); a round-trip test serialises every official card
   and power and checks the loaded definition equals the static one.
   Golden identical; no state change.
2. **Content in the versions:** built as content identity (decisions
   "Runtime registry stage 2: records name their packs, the store recovers
   them; versions stay official-only"): packs a record names are stored
   by hash in `datasets/packs/` (`registry.store_pack`), and replay loads
   a missing one from there (`registry.ensure_content`, checked against
   its hash). The fingerprint and `rules_version` stay official-only until
   the codec can write generated states; stage 4 hashes the official
   content files into the fingerprint.
3. **Monsters from packs:** built (decisions "Runtime registry stage 3
   spec: monsters from packs as process-wide kinds"): a pack's `monsters`
   (HP, moves, pattern rows, start block and official powers, split) load
   as kinds numbered from 19 in load order; `CombatState::new_vs` and
   `sts.Combat.versus` fight them; 13 of 18 official monsters round-trip
   and play the same; the lice, Lagavulin, Hexaghost and The Guardian
   (code-only parts) stay official-only. Generated powers on monsters are
   refused at load.
4. **Official content as files:** `content/*.json` generated from today's
   tables, loaded at startup, checked equal to the tables, then the tables
   go (or stay as the fallback; owner's call). Built (spec
   `docs/specs/official-content-files.md`): the tables are gone; the files
   are the source and are hashed as rules.
5. **State representation:** sorted inline piles of (`u16` id, count) and
   sparse power lists, sized for open-ended content and smaller than
   today's arrays for typical states (the speed lever); registry per
   process vs a handle the state points to (cargo runs tests as threads
   of one process; `generated-cards` wants content per run).
   Specced (`docs/specs/sparse-state.md`, with its measured speed case):
   sorted inline lists per pile and per creature; the registry stays one
   per process. Not built yet.

## Questions for the owner

1. Stage order: the re-scope says generated attacks / skills first (stage
   1) and retrain after each step; the umbrella puts the representation
   first. Recommendation: stage 1 then 2 (small, unblock training on
   generated attacks), then 5 before content outgrows `u8` ids.
2. Keep the static Rust tables as the official source with files exported
   from them, or make the files the source (stage 4)?
3. Registry scope: one per process (today) or a handle per state?
4. Speed budget for stage 5: is a separate "search memo stores each state
   once" speed spec wanted first (it would recover the series' search cost
   on its own)?

## Fits with (every stage)

Golden games and proving sets identical; codec encodings identical for
official content; heuristic and contract nets bit-identical
(`scripts/series_check.py`); H4 (`two_turn_phases --check`) identical;
speed per `scripts/series_speed.py`.
