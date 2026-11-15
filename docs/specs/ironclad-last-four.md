# The last four Ironclad cards

Status: closed (2026-11-14, built and in use: steps 1-2 Battle Trance, Reaper; steps 3-4 Dual Wield, Juggernaut; Ironclad cards 75 of 75; kb measurement/act1-cards@files).

Research: `docs/research/ironclad-last-four-2026-11-14.md`. One reader per
card read its class in the installed jar and the engine; a skeptic per card
re-read both. Each step's builder reads its card's entry and the skeptics'
checks there first: the game facts, the draft entries and the corrections
are not repeated here.

## Outcome

Battle Trance, Dual Wield, Juggernaut and Reaper load from
`content/packs/act1-ironclad.json` (and the Ironclad pool) and act as the
game's classes. Ironclad cards reach 75 of 75 (`docs/INDEX.md`), so no
Ironclad card in a real run's piles drops the bridge's fight to its
fallback player. Each piece is a general word any pack content can use.

## Steps

### Step 1: Battle Trance (S)

A replacement event on draws, `Replaced::Draw`, accepting `Cancel` only
for now; checked when a draw is requested (`chance.rs` `request_draw`),
so the card's own draw, requested before the power applies, goes through,
and later draws this turn (Pommel Strike, Dark Embrace, Evolve) don't.
Pack power No Draw (debuff, removed at the owner's turn end); card: Draw 3
(+1), then No Draw.

### Step 2: Reaper (S)

A quantity for the HP the user's latest damage effect took (summed over
targets and hits, each hit capped at the target's HP), and a heal from it.
Reaper: damage 4 (+1) to all, then heal that much; exhaust. The research's
skeptic notes refine the order (per-target vampire damage): follow them.

### Step 3: Dual Wield (M)

A type filter on any pick (`of`: a set of card types, default all), and
an effect copying the picked card into hand (n copies, +1 upgraded; a full
hand sends them to the discard pile, as the game does). Dual Wield picks
an Attack or a Power.

### Step 4: Juggernaut (M)

`Trigger::OwnerGainedBlock` (the game's `onGainedBlock`: once per block
gain above 0, after Dexterity, Frail and relic modifiers) and a hook dealing
damage to a random monster, through the random-work queue blocked-relics
step 5 built. Juggernaut: power, 5 (+2) damage per block gain. The
skeptic's correction (the Curl Up example) applies.

## Rules for every step

- New words in `registry::element_names()` with words in
  `content/wording.json`; explorer wording pin re-recorded (additions
  only); game ids in `content/game_ids.json` (`scripts/game_ids.py check`
  says 0 missing).
- Tests per card, base and upgraded, against the jar classes; the
  research's test list is the minimum.
- Golden must not change; if it would, stop and report to the manager.
- Owner's test budget: debug engine tests covering the change plus golden;
  no full suite, release tests or speed checks. `CARGO_BUILD_JOBS=2`;
  never `cargo fmt`.
- Landing: rebase on main, lock `act1-release`, one release wheel from
  current main (keeps `Combat.view`), `jobs.py impact sts` in the commit,
  swap main's `sts`, push; `scripts/docs_index.py --write`; tell the
  bridge session (`bridge-runs`) what landed.

## Verification

Done when the four cards load with passing tests, golden is unchanged, and
`docs/INDEX.md` shows 75 of 75 Ironclad cards.
