# Exhaust another card (building block C1)

Status: closed (2026-11-06, built and in use; lane act1-content block C1; a0a9bdaa; checkpoint c1-built passed, 2296bac9).

## Outcome

A pack card can exhaust cards other than itself (one the player picks, a
random one, or every card in hand of a type) and return one from the
exhaust pile, so the six Ironclad cards blocked only by C1 load from a pack
file and play correctly: True Grit, Burning Pact, Second Wind, Sever Soul,
Fiend Fire and Exhume (12 entries with upgrades).

**How it moves the goals.** Goal 1 asks for first-class custom content: a
designer's card that says "exhaust a card" or "exhaust your hand" cannot be
written today, and exhaust is a whole archetype of Ironclad. After this, it
is data. Goal 2 needs the real Act 1 card pool; these six are a quarter of
the 24 blocked cards, and C2 (a trigger on exhaust: Dark Embrace, Feel No
Pain, Sentinel) only means something once C1 exists. We'll know by the
lane's measure: the blocked count drops from 24 to 18, each new entry is
checked against the wiki in a test, and the series checks hold (golden
identical, `series_check` PASS, `series_speed` at most +10%).

**Non-goals.** C2 (exhaust triggers) is the next spec; Corruption (needs C5)
and Havoc (needs C8) stay blocked. The random-content generator's
vocabulary is unchanged. No official card changes, so the rules version
stays. No retraining, no headline read: the new cards are pack content
outside every training pool.

## Behavior

New pack vocabulary (JSON in pack `effects`, the same shapes the writer
emits):

| JSON | What it does |
|---|---|
| `{"Pick": {"kind": "ExhaustFromHand", "n": 1, "exact": true}}` | The player picks a card in hand; it goes to the exhaust pile. Skipped with an empty hand. |
| `{"Pick": {"kind": "ReturnFromExhaust", "n": 1, "exact": true}}` | The player picks a card in the exhaust pile; it goes to hand. No pick while the hand is full (as `ReturnFromDiscard`). A card whose own effects hold a `ReturnFromExhaust` pick is never a candidate (the game's "not Exhume", stated by mechanic, not by name); skipped when nothing is a candidate. |
| `"ExhaustRandom"` | One uniformly random card in hand (by copies) goes to the exhaust pile: a chance event (`ChanceEvent::RandomExhaust`) while the hand holds more than one distinct card; resolved at once with one distinct card; nothing with an empty hand. |
| `{"ExhaustHand": {}}` / `{"ExhaustHand": {"except": "Attack"}}` | Every card in hand (or every card not of that type) goes to the exhaust pile. |
| `{"ScaledBlock": {"amount": 5, "times": <amount>}}` | Block `amount` gained `times` times (Dexterity and Frail apply to each). |
| amount `{"base": 0, "k": 1, "of": {"HandCards": {}}}` (or `{"HandCards": {"except": "Attack"}}`) | Quantity: cards in hand (or not of that type) when the effect resolves; the card in play is not in hand. |

Count-then-exhaust: a card that scales with the exhausted cards reads
`HandCards` in an effect placed before its `ExhaustHand`. Without exhaust
triggers (C2) this is the same fight as the game's exhaust-then-count; C2's
spec re-checks the order.

The six cards (base / upgraded; numbers from the wiki, checked against
sts_lightspeed in build step 1):

| Card | Cost | Type | Entry |
|---|---|---|---|
| True Grit | 1 | Skill | Block 7 / 9; base `ExhaustRandom`, upgraded pick `ExhaustFromHand` 1 |
| Burning Pact | 1 | Skill | pick `ExhaustFromHand` 1; Draw 2 / 3 |
| Second Wind | 1 | Skill | `ScaledBlock` 5 / 7 times `HandCards` except Attack; `ExhaustHand` except Attack |
| Sever Soul | 2 | Attack | `ExhaustHand` except Attack; Damage 16 / 22 |
| Fiend Fire | 2 | Attack | `ScaledDamage` 7 / 10 with hits `HandCards`; `ExhaustHand`; exhaust |
| Exhume | 1 / 0 | Skill | pick `ReturnFromExhaust` 1; exhaust |

Edge cases: every exhaust goes through one engine function (`exhaust_from`,
hand or exhaust-pile bookkeeping and the variant drop), so C2 adds its
trigger in one place. Picks, `ExhaustRandom` and `ExhaustHand` are refused
in hooks and turn-end effects at load, as picks and random hits are now
(`runs_outside_a_card`); `ExhaustHand` and `ScaledBlock` may run anywhere
`Block` can. A replayed copy (Double Tap on Fiend Fire) counts the hand
again, which is empty: 0 hits, as in the game.

## Fits with

| Neighbour | Must stay true | Pinned by |
|---|---|---|
| Official content, rules version | golden identical; every official card round-trips | `golden.rs`, `official_files.rs` |
| Existing picks (Survivor, Hologram, Headbutt) | same legal actions and results | `decisions.rs` |
| Codec | every state round-trips, new pick kinds and chance event included (the codec holds official content only, so they are checked on an official state set to each); old encodings decode the same | `codec.rs`, `exhaust.rs` |
| Chance outcomes / search / exact solver | outcome lists sum to 1; sampled and listed agree | `exhaust.rs` (`true_grit_random_is_chance`) |
| Solver bounds | no new effect heals | `Effect::heals` (compile-time: no catch-all arm) |
| Net features (`py/src/features.rs`) | a net's stored layout gathers the same columns as before; new columns only in the full layout | `scripts/tests` features tests, plus `layout_names` of the product net unchanged (step 4) |
| Heuristic | estimates on existing content unchanged | `series_check` |
| Render (`py/src/render.rs`) | names the chance event (picks aren't rendered, as before) | `scripts/tests/test_render.py` |
| Pack writer (registry JSON out) | new effects written in the shapes above and read back equal | `exhaust.rs` round-trip of the 12 entries |
| Speed | `series_speed` at most +10% | `scripts/series_speed.py` |

**When in doubt:** prefer the game's behaviour as sts_lightspeed codes it
over a neater engine rule, except where `decision/parity-source` says the
wiki decides.

## Scope

May change: `engine/src` (effects, state, chance, codec, registry parse and
write, heuristic, bound), `py/src` (features, render), `engine/tests`,
`content/packs/act1-ironclad.json`, `docs/research/act1-inventory.md`,
this spec. New JSON effect, pick-kind and quantity names as above; the
codec gains tags (pick kinds 4 and 5, chance event 4) without changing old
ones.

Off limits: official content files and anything that changes golden;
`Action` and the decision interface (picks reuse `Choose`/`Done`); the
generator; training, gauntlet and run-layer scripts.

## Decisions taken

- (on the owner's behalf) Exhume's exclusion is by mechanic (a card with a
  `ReturnFromExhaust` pick), not by card name: the same in the game for
  official content, and it keeps a designer's "exhume" card from looping.
  Alternative: exclude the card in play's id and its upgrade (by name).
- (on the owner's behalf) Count-then-exhaust instead of a per-card counter
  in `InPlay`: no codec or state change; identical fights until C2, whose
  spec re-checks it. Alternative: a count field in `InPlay`.
- (on the owner's behalf) True Grit's random exhaust is a real chance
  event, so search and the exact solver see it as chance. Alternative:
  leave base True Grit blocked (only True Grit+ writable).

## Outside assumptions

- The six cards' costs, numbers, types and exhaust flags as in the table:
  checked against the wiki's Ironclad card list and sts_lightspeed
  (`Cards.h`, `BattleContext.cpp`) in build step 1; a difference follows
  `decision/parity-source` and is written into the inventory.
- sts_lightspeed: True Grit picks uniformly among hand cards; Exhume does
  nothing with a full hand and skips Exhume copies; Second Wind and Sever
  Soul exhaust Status cards (non-Attacks). Checked in step 1.

## Verification

Tests first (`engine/tests/exhaust.rs`, packs from `act1-ironclad.json`):
- `burning_pact_exhausts_pick_then_draws`: hand Strike, Defend, Bash; play
  Burning Pact, Choose Bash; Bash in exhaust, hand 2 + 2 drawn; with an
  empty hand no pick, still draws 2.
- `true_grit_random_is_chance`: hand Strike x2, Defend; play True Grit;
  pending `RandomExhaust`; outcomes Strike 2/3, Defend 1/3, each with 7
  block; one distinct card resolves at once; True Grit+ offers Choose per
  distinct card.
- `second_wind_counts_non_attacks`: hand Strike, Defend x2, Wound;
  Second Wind gives 15 block (3 x 5), with Dexterity 2 gives 21; Strike
  stays; exhaust holds Defend x2, Wound, Second Wind goes to discard.
- `sever_soul_and_fiend_fire`: Sever Soul exhausts non-Attacks, deals 16;
  Fiend Fire with 4 cards in hand deals 4 hits of 7 (Strength 2: 4 x 9),
  exhausts the hand and itself; with an empty hand 0 damage.
- `exhume_returns_not_exhume`: exhaust holds Bash, Exhume; Exhume offers
  only Bash; full hand: no pick; only Exhume copies there: no pick.
- Hook refusal: a generated power with `ExhaustHand` in a hook loads;
  with `ExhaustRandom` or an exhaust pick it is refused with a message.
- Codec and chance round-trips for a state paused at each new pick and at
  `RandomExhaust`.
- A mutation check: Second Wind+ times 6 and Exhume with the exclusion
  removed each fail a test.

End to end: a greedy player with the starter deck plus the 12 entries (two
decks under the 8-slot limit) beats a Jaw Worm in 40 of 40 seeds, picks
included. (The exact solver keys states by the codec, which holds official
content only, so it does not run on pack decks; found in the build.)

Don't guard: run-layer card rewards for these cards (the 8-slot limit and
the missing upgrade link are the run layer's, inventory "Left for later");
encodings from builds before this one beyond what `codec.rs` already
checks.

## Build steps

1. Write the tests above and the pack entries; check every number against
   the wiki and sts_lightspeed and write the result into the inventory.
   Check: the tests compile against stubs and fail only on the missing
   behaviour; existing suites pass.
2. Engine: `PickKind::ExhaustFromHand`, `ReturnFromExhaust` (with the
   exclusion), the `exhaust_from` funnel, `ExhaustHand`, `ScaledBlock`,
   `Quantity::HandCards`; registry parse and write; codec tags. Check: the
   pick, Second Wind, Sever Soul, Fiend Fire and Exhume tests and the
   codec and pack round-trips pass; golden identical.
3. `ExhaustRandom` and `ChanceEvent::RandomExhaust` (listed outcomes,
   sampling, codec, hook refusal). Check: the True Grit and chance tests
   pass.
4. `py/src`: feature columns for the new effects, pick kinds, quantity and
   chance event (full layout only); render names; heuristic estimates
   (ScaledBlock as amount x an expected hand count, exhausts 0). Check:
   features tests pass; the product net's `layout_names` unchanged; a
   gauntlet sanity run of the product on 20 sequences gives identical
   results to before.
5. End to end and series checks: the greedy and solver checks above;
   `series_check` PASS, `series_speed` at most +10%; inventory counts
   updated (blocked 24 -> 18). Check: all pass and recorded in the
   inventory.

Build plan: 5 steps, in-session (steps 1-3 share one engine context),
on Opus. No stop points: every decision above is reversible.
