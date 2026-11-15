# Series review fixes: defects found in engine-next before it lands

Status: umbrella (2026-11-02, part 1 (pre-landing slice) built 2026-11-02 (5109ba8 A1, 81f823c E4); part 2 generator-hardening bundle and part 3 backlog unbuilt; decisions 'Series review fixes: the cut').

Written from a max-effort code review of
`git diff main...HEAD` on branch `engine-next` at `d9327a2` (the next
commit, `b2c322a`, only adds a research doc; the code is the same).

## The cut (read this first)

An independent check found every top finding real, but only A1 reaches the
official training pipeline. B1 and B2 are generated-content rule bugs that
are older than the branch (main has them). Everything else needs a
hand-written content pack or crafted bytes that nothing in the project
produces today. So the spec is built in three parts; the rest of this file
and the group files stay as the catalogue of findings.

**Part 1: pre-landing slice (confirmed; build now, on `engine-next`).**

1. **A1, owner decision 1 option (b).** `stsnet.widen` takes named row
   kinds and never drops one of the parent's; `finetune.py` names today's
   default kinds (triggered, threshold, held) plus any kind the parent opted
   into, encodes train, validation and replay with that layout and refuses
   a widened layout that differs from it. Details: `A-training.md` step
   A-1 (both its tests, with (b)'s expected kinds).
2. **A finetune config key for the opt-in row kinds.** `extra_rows: true`
   adds every opt-in kind (static, countdown, replacement, pattern);
   `row_kinds: [...]` adds the named ones (unknown names refused). Both add
   to the kinds of item 1, for warm and fresh starts, so the series' planned
   rows-on vs rows-off burst can train both arms with `finetune.py`. Test
   first: `scripts/tests/test_warm_start.py::test_finetune_extra_rows` (a
   tiny warm fine-tune with `extra_rows: true` saves all seven kinds and
   every encoded set has that layout; a misspelled `row_kinds` entry
   raises).
3. **Outcome check in `registry.replay`** (owner decision 2 option (a)).
   As "Step 2 in detail" below.
4. **H1** (owner decision 3 option (a)): mark
   `docs/specs/runtime-registry.md` "DRAFT, not queued"; correct
   `docs/engine-next.md`.
5. **E4:** the rules fingerprint hashes `engine/src/registry.rs`. Details:
   `E-variants.md` step 4.

Checks for the slice: `cargo test --release -j 4`; the Python suites the
touched code reaches (`test_warm_start.py`, `test_finetune_gen.py`,
`test_curve.py`, `test_registry.py`, `test_branches.py`, `test_hp_loss.py`,
`test_setups.py`, `test_survival_score.py`, `test_contract.py`); golden.txt
and codec_golden.txt unchanged; `scripts/series_check.py` PASS with "old"
dumped from main's module (the shared venv) and "new" from this branch's
(`target/pyroot`), cards "Body Slam,Heavy Blade,Perfected Strike" and the
three contract nets.

**Part 2: generator-hardening bundle (written down, not built now).** Built
together with extending `scripts/gen_content.py` from powers to attacks and
skills: that is when generated content starts to reach these paths, and the
generator can be made to avoid what the loader refuses.
- **B1** (hook and turn-end draws) and **B2** (a split or Close Up set
  during the monster's own move), both already on main, in generated play.
- **C1-C5** (hook effects: replayed copies, hook hits, stacks, counts,
  CardInPlayTagged).
- **D1-D7** (loader validation and search's pick bound). **D7 is widened:**
  the loader refuses GrowDamage in pack *hooks* as well as on pack cards.
  No pack and no generator writes it, and with it gone a pack can no longer
  grow the card in play, which retires most of E1 (a hook grows the card in
  play), E2's Power-card path (a hook grows a Power card) and C3's
  GrowDamage part. Re-check what is left of E1, E2 and C3 when the bundle
  is built.
- The order inside the bundle follows "Full step order" below (steps 3-20,
  with steps 8 and 10 reduced as above), each with its group file's
  details. Owner decision 2's outcome check (part 1) lands first, so a
  generated dataset that replays differently after B1 or B2 fails loudly.

**Part 3: backlog (not scheduled).** A2-A5, B3, E3, E5, E6, what D7's
widening leaves of E1 and E2, F1-F4, G1-G4, K1-K20 and the unverified
follow-ups at the end of this file. Each entry stays as written; pick one
up when its path becomes reachable (for example E3 and E5 when the codec
starts to encode pack states, F1 when records hold grown variants).

The sections below are the original spec, kept as the catalogue. Where
they say "every finding A1-H1 is fixed", read the cut above instead.

## How to use this spec

You can build from this spec alone, without the review that produced it.

- **Read this file first** (it is short): Why, Fits with, Decisions, How to
  build and check, then the Build steps in order.
- **The findings live in one file per group** under
  `docs/specs/series-review-fixes/`. Each file holds the group's findings
  (where the defect is, what goes wrong, how to reproduce it as a failing
  test, the fix, the test to write first, what must not move), then the
  group's step details (files, size, acceptance check) and the pins it may
  change. Read a group file when a step sends you there; don't load them all
  at once (about 50-60 KB each). Grep for a heading such as `### C1.` to find
  one finding.

| Group | File | Findings |
|---|---|---|
| A. Training pipeline and features | `A-training.md` | A1-A5 |
| B. Chance and turn order | `B-chance.md` | B1-B3 |
| C. Hook effects | `C-hooks.md` | C1-C5 |
| D. Pack loader validation | `D-loader.md` | D1-D7 |
| E. Variants and codec | `E-variants.md` | E1-E6 |
| F. Python tooling | `F-tooling.md` | F1-F4 |
| G. Tests that can't fail | `G-tests.md` | G1-G4 |
| H. Docs and conventions | this file | H1 |
| K. Optional cleanup (not bugs) | `K-cleanup.md` | K1-K20 |
| X. Refuted claims (don't redo) | this file | - |

- **Review numbers.** The review's panel reported 15 findings, numbered by
  severity: #1 A1, #2 B1, #3 B2, #4 C1, #5 C2, #6 D1, #7 E1, #8 E2, #9 F1,
  #10 A2, #11 B3, #12 C4, #13 C5, #14 C3, #15 D2. Everything else here was
  verified too, but cut from the panel by its 15-finding cap.
- **How it was checked.** An independent verifier checked every finding
  against the code at `d9327a2`, most by running a throwaway test. A second
  agent then read each entry as a builder would and corrected it against the
  code. Line numbers are at `d9327a2` and drift as you edit: find code by its
  content.
- **Terms** (the project's own; each group file explains them again where
  they matter):
  - a *content pack* (pack) is JSON that defines generated cards and powers
    (`engine/src/registry.rs` loads it);
  - the *binding* is the per-combat table that maps card and power ids to
    their definitions;
  - a *variant* is an official card with a per-copy override (a grown
    Rampage), held in one of the binding's 4 slots;
  - a *hook* is a power's rule "when X happens, do these effects", and a
    *static* is a power's damage or block modifier row;
  - the *known top* is the part of the draw pile whose order is known
    (Headbutt puts a card there);
  - *row kinds* are the families of feature rows a net reads;
  - *proving content* is official content added to prove one spec
    (Whirlwind, Caltrops, Burst, Hologram, Headbutt, Rampage, Protect,
    Accuracy and others), kept out of every training and eval pool.

## Why

The branch builds the rules-engine series (specs 2, 4-9 and spec 10 stage
1) and waits to land on main (`docs/engine-next.md`, "Landing"). The review
found:

- **One defect that breaks the official training pipeline:** a warm
  fine-tune trains on feature rows that its saved net then drops (A1).
- **Two defects that already change training games with generated
  content.** Both are older than the branch; the branch adds routes to the
  first, and its notes understate the second. B1: draws asked for by hooks
  are lost or made late. B2: a slime or the Slime Boss loses its split, and
  The Guardian its Close Up, when damage reflected during its own move
  takes it past the threshold.
- **Defects reachable only through content packs,** where the loader
  accepts content that the engine then mishandles: an endless replay loop,
  a stack overflow, unbounded search, amounts that ignore stacks, a card
  filed under a stale id, wrong draw odds (B3, C, D, E).
- **Tooling, test and doc gaps** (F, G, H).

Spec 10's goal is that packs carry every atom, and generated content is
where the project is going. So pack-only defects matter: a generated or
hand-written pack that hits one can hang a job, kill a process, or quietly
teach a net wrong rules. Fixing them before landing means main never
carries them.

How we'll know: each finding's "Test first" fails on `d9327a2` and passes
after its step, and every check under "Fits with" holds.

## Outcome and non-goals

Outcome: every finding A1-H1 is fixed, with a test that failed before the
fix, or closed the way its entry says (a few low findings are closed by
documenting them). Official-content behaviour and every pin listed under
"Fits with" stay byte-identical, except where an entry names the pin and
says why.

Non-goals:

- The optional cleanup in `K-cleanup.md` (separate steps, later, only if
  wanted).
- The follow-ups found while writing this spec (not verified; listed at the
  end for a later review).
- New content, new feature columns beyond what an entry names, or
  retraining any net.
- Landing the branch on main. That is `docs/engine-next.md`'s "Landing"
  procedure, after this spec.
- Spec 10 stages 2-5 (`docs/specs/runtime-registry.md`).

## Fits with: what must stay true

- **`engine/tests/data/golden.txt`:** the 9,000 official games replay
  byte-identical after every step (`cargo test --release -p sts-engine
  --test golden`). Its hash is the registry's rules version
  (`scripts/registry.py` `rules_version()`, `7042d1d6a6149ba0` at
  `d9327a2`), so recorded datasets stay usable.
- **`engine/tests/data/golden_proving.txt`** (seven proving sets:
  whirlwind, accuracy, wraith, survivor, hologram, headbutt, rampage):
  byte-identical. The one exception: B2 may change
  `proving-wraith:silent:large_slime:*` and
  `proving-wraith:silent:slime_boss:*` lines, where Caltrops' Thorns takes
  a slime to half HP during its own attack and the split is now kept.
  Re-record only those lines, and say why in the commit.
- **`engine/tests/data/codec_golden.txt` and every existing encoding:**
  byte-identical; `CODEC_VERSION` stays 1. The decoder fixes (E3, E5)
  refuse only bytes the engine never writes. B3 writes its floater count as
  a varint, the same single byte below 128. (K8, optional, is the only item
  that changes bytes, for states no stored data holds.)
- **solvedb's content-table pin** `content_tables_pinned`
  (`0x5a922915c8ae26dd`): unchanged. No card, power, monster or move is
  added.
- **The rules fingerprint** (`solvedb::fingerprint()`, over the files in
  `solvedb/src/fingerprint.rs`): changes, as expected. Code edits to
  state.rs, chance.rs, effects.rs and hooks.rs move it (comment-only edits
  don't: it strips comments), and E4 adds registry.rs to its files. The
  branch already changes it, so the solved DB is retired at landing as
  planned. No test pins its value.
- **`scripts/series_check.py`:** PASS against a baseline dumped from this
  worktree's module built at `d9327a2`: heuristic and contract nets
  bit-identical, every feature column equal by name.
- **H4 search identity:** `cargo run --release --example two_turn_phases
  100 --check <file>` writes a file byte-identical to the one recorded at
  `d9327a2`.
- **Python pins:** `scripts/tests/data/contract/pins.json`, `outputs.npz`,
  `old_layout.json` and the tiny nets; `py/tests/data/golden_rows.npz`;
  `scripts/tests/data/lookahead_off_names.json` and `lookahead_rows.npz`;
  `TRAIN_PIN` (`scripts/tests/test_net.py`); `GAMES_PIN` and `ARRAYS_PIN`
  (`scripts/tests/test_content_selfplay.py`);
  `scripts/tests/data/curriculum_pins.json`. All unchanged. The one
  expected test edit is F1's: `scripts/tests/test_contract.py:504` expects
  the reworded NotSupported message.
- **Confirmed decisions stand:** the series row kinds are opt-in
  (`docs/decisions.md`, "Series row kinds are opt-in"); an X card's cost
  stays 0 for every cost reader (spec 2); OwnerPlaysCard doesn't fire for
  replayed copies (spec 6).
- **`CombatState` size:** B3 adds 8 bytes; no other step may grow it.
  Memory is this machine's binding limit; `two_turn_phases` and `bench`
  print the size.
- **Generated-content play changes on purpose** under B1 and B2, and for
  content no pack in `data/` holds under C, D and E. See owner decision 2
  about generated datasets recorded before the fix.

## When in doubt

Prefer refusing content at load, with an error that names the pack entry,
over defining new play rules for it. Prefer fixing the shared rule in the
engine over a special case at one call site. Prefer keeping official-content
behaviour and every pin byte-identical over any other gain.

## Scope

May change:

- `engine/src`:
  - the loader's validation (`registry.rs`);
  - the rules, where an entry says (`state.rs`, `chance.rs`, `effects.rs`,
    `hooks.rs`, `agent.rs`; `powers.rs` for D5's optional sites; `cards.rs`
    only under E4's alternative);
  - search (`search.rs`, D1);
  - the codec (`codec.rs`): the decoder's validation (E3, E5), and the
    floater count written and read as a varint (B3);
  - the heuristic (`heuristic.rs`, D3 (b) only, optional);
  - doc comments.
- `engine/tests`: new tests; the fixed tests (G1-G4, E6); D7's change to
  `packs.rs::every_official_card_round_trips` and the file's header doc;
  the test helpers E2, E3 and F4 change (`common/mod.rs`'s
  `check_invariants`, `golden.rs`'s `dump`).
- `py/src`: `features.rs` (A2 and D5, plus the comments the A and D3
  entries name) and `lib.rs` (F2, and F3's optional `solve` guard).
- `scripts`: `finetune.py` and `stsnet.py` (A1); `registry.py`,
  `action_text.py`, `bench_decisions.py`, `bench_probes.py` and
  `analysis/pattern_value_error.py` (F1, step 2); their tests under
  `scripts/tests` and `py/tests`.
- `solvedb/src/fingerprint.rs` (E4) and its test.
- Docs: the `docs/decisions.md` entries the fixes correct and one new
  entry for this spec,
  `docs/specs/rules-engine-upgrade.md`, `docs/extending.md`,
  `docs/engine-next.md`, `docs/specs/exact-solver.md` (E4), the README's
  pack section, and `docs/specs/runtime-registry.md` (H1 only).

Interfaces that change:

- The pack JSON contract gets stricter: packs that load today may be
  refused. `data/bench/gen_powers_pack.json` and every pack the training
  configs use must still load.
- `sts.run(forced=...)` refuses a forced action whose card name doesn't
  match the game's (F2).
- The decoder refuses more byte strings (none the engine writes).
- `registry.replay` raises when a replayed game's outcome differs from the
  recorded one (step 2, if owner decision 2 takes option (a)).

Off limits:

- Re-recording `golden.txt` or `codec_golden.txt`, or a Python pin that
  no entry names. (A2 names one case: a feature pin holding a state with
  6+ Brutality stacks may move, since the draw is now capped at 10;
  re-record it and say why. Golden decks hold at most one Brutality+, so
  it isn't expected.)
- The contract nets.
- The shared `.venv`: never `maturin develop` or `pip install` into it
  (AGENTS.md).
- Main's checkout, `db/`, `models/` and `runs/`.
- The job queue (`scripts/jobs.py`).

## Decisions

### For the owner (stop points)

Answered 2026-11-02 by the manager with the owner present: 1 (b), 2 (a),
3 (a); see "The cut" and `docs/decisions.md` "Series review fixes: the
cut".

1. **A1: which row kinds a warm fine-tune trains on and saves.** It is
   expensive to reverse because every fine-tune saved afterwards carries
   the choice. Runs on either side of a switch read different inputs, so
   they can't be compared or pooled without re-running them. Either way,
   `finetune.py` will encode train, validation and replay with exactly the
   layout it saves, and `widen` will accept named kinds but refuse to drop
   one; that part is must-fix and is built first.
   - **(b) Recommended: today's default kinds (triggered, threshold, held)
     plus any kind the parent opted into.** A fine-tune of a parent saved
     before threshold and held rows learns and keeps those rows. Such
     parents are `models/value_effects.pt` (curve.py's warm_effects
     parent) and the 2026-10-29 champion
     (`runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt`, the parent of
     the 0059 burst fine-tunes). This is what main's fine-tunes did: the
     0059b1 arm `runs/2026-11-01-burst8-s1-d4b65b6` saved `[triggered,
     threshold, held]`. It is also what the threshold-and-held-rows spec
     intended (`docs/specs/threshold-and-held-rows.md:108-109`). Cost:
     before training, the widened net reads threshold and held rows its
     parent never saw, so its first-epoch scores on boss and slime states
     differ from the parent's, as they did on main.
   - **(a) The parent's own kinds.** The widened net starts exactly as its
     parent. But fine-tunes of old parents never learn from Mode Shift,
     slime-split or Burn rows. New fine-tunes would also differ in inputs
     from main's 0059 arms, which confounds comparisons across the
     landing, and `curve.py`'s `find_run` (curve.py:205-223) reuses runs
     by config, parent and rules version, none of which records row kinds.
2. **Generated datasets recorded before B1 and B2.** B1 and B2 change how
   games with generated packs play; official-only play doesn't change, so
   golden.txt (the only rules version `scripts/registry.py` checks) stays
   the same. 31 of the 215 datasets under the main checkout's `datasets/`
   carry a `content_hash` in `manifest.json`. `registry.find` will still
   reuse them, and `registry.replay` copies the recorded outcome instead of
   checking it, so a game that hit a changed path replays differently from
   that point, silently. Bench scores on the gen_powers sets recorded
   before the fix aren't comparable for the fights these paths reach.
   - **(a) Recommended:** land the fixes; make `registry.replay` check
     each replayed game's outcome and raise on a mismatch (build step 2),
     so a diverging game fails loudly; keep using existing feature caches;
     re-record a generated dataset only when a job needs to replay it; note
     the landing commit in `docs/manager.md`.
   - (b) Re-record all 31 datasets now (machine time, the project's
     bottleneck).
   - (c) Build spec 10 stage 2 first (versions that hash loaded packs, and
     a generated-rules epoch), so the version check retires exactly these
     datasets.
3. **H1: the committed draft spec** `docs/specs/runtime-registry.md`.
   **(a) Recommended:** keep it, marked "DRAFT, not queued" like main's
   deliberate drafts, and correct `docs/engine-next.md`. (b) Remove it from
   the branch. See H1 below.

### For the manager (cheap to reverse; each entry gives the recommendation)

- **D7:** refuse GrowDamage on pack cards (`card_json(Rampage)` then no
  longer loads). This doesn't decide the owner's open question about letting
  generated cards grow (spec 10 stages 2-5); it turns a silent no-op into an
  error. Recommended: refuse.
- **D3 (a):** refuse the ScaledDamage shapes the features and heuristic
  can't read (two-sided, CardsTagged other than Strike, EnergySpent outside
  an X card's play, an amount with `k` but no `of`). This adds no feature
  columns, so every Python pin stays. D3 (b), a heuristic fallback, is
  optional: skip it if "the heuristic stays blind through the series"
  covers new atoms.
- **D4 step 3:** leave card, power and pack objects unchecked for unknown
  keys, because the generator's metadata keys live there; say so in the
  README.
- **E3:** a full variant table stops play with a panic instead of silently
  freezing a card's growth (packs and crafted bytes only).
- **E4:** hash all of `engine/src/registry.rs` in the fingerprint
  (recommended), or move the variant rules into `cards.rs`. Settle it before
  the solved DB is refilled after the series: changing the fingerprint's
  files later retires the refill again.
- **K8 (optional cleanup):** merge codec tag 7 into tag 8 before landing,
  or drop it.

### Taken in this spec (provisional; the build copies them into `docs/decisions.md`)

- Two rules follow the game: a replayed copy is never replayed again (C1,
  a guard in `do_effect`; the loader keeps accepting ReplayCard under any
  trigger), and a hook's hit still goes through the attack pipeline
  (Strength, Weak, Vulnerable, statics, replacements, block) but, like
  Thorns, fires no OwnerAttacked hooks (C2).
- A draw asked for while another waits joins it as one draw (B1 part 1);
  a monster's Draw draws for the player (part 3); an after-card hook's
  draw is made before the card goes to its pile (part 4). A split or Close
  Up that `lost_hp` sets during or after the monster's own move survives
  the end-of-turn roll (B2; Lagavulin's stun stays open). Known-top
  floaters are one entry per distinct (card, above), with a copy count
  (B3).
- The pack loader refuses what play can't do, each as its entry says:
  Draw in a card's `turn_end` or in an `OwnerTurnEnd` hook (B1 part 5); a
  negative cost, or an X card whose cost isn't 0 (D2); official power
  names as pack power ids (D6); ScaledDamage shapes per D3; GrowDamage on
  a pack card (D7; power hooks may still hold it); and, per D4, values of
  the wrong JSON type, numbers outside their field's range, unknown keys
  inside rows, hooks, triggers, statics, replacements, effects and
  amounts, and more than 255 effects in a card's play rows.
- Past the node cap, search still expands a pick, along its first option
  only (D1). Damage, block and replacement arithmetic saturates at the
  i16 range instead of wrapping (D5; step 17 also makes `grow_damage`'s
  `damage + k` saturating).
- The decoder validates before it interns a variant and refuses a listed
  variant no card holds (E3), and refuses picks the engine never makes
  (E5).

## How to build and check in this worktree

- **Where:** `.claude/worktrees/engine-next` (inside the main checkout),
  branch `engine-next`. The job runner and its jobs load `sts` from main's
  `.venv`; never install into it.
- **Rust:** `cargo test --release` runs every engine and solvedb test
  (golden, codec and fuzz included). One binary: `cargo test --release -p
  sts-engine --test <name>`. A debug run (`cargo test -p sts-engine --test
  <name>`) also checks integer overflow and `debug_assert!`; use it where an
  entry says.
- **Python module:** `bash scripts/dev_sts.sh` builds this checkout's `sts`
  into `target/pyroot`. Before you run it, check that no Python process of
  this worktree is still using `target/pyroot` (`tasklist //FI "IMAGENAME
  eq python.exe"` lists every Python process, the job runner's too; in
  PowerShell, `Get-Process python | Where-Object { $_.Modules.FileName
  -like '*target*pyroot*' }` shows only the ones holding this module).
- **Python:** run from the worktree root as `PYTHONPATH="$PWD/target/pyroot"
  ../../../.venv/Scripts/python.exe <file>`. Test files run directly (the
  venv has no pytest) and print one line per test.
- **series_check:** one baseline, `target/sc_head.npz`, dumped at step 0
  with this worktree's module built at HEAD before any edit; later dumps
  use the module after your changes; then compare. Every dump takes the
  same arguments, the cards right after the output file and the nets after
  them:
  `PYTHONPATH="$PWD/target/pyroot" ../../../.venv/Scripts/python.exe
  scripts/series_check.py dump <file>.npz
  --cards "Body Slam,Heavy Blade,Perfected Strike,Whirlwind"
  models/value_effects.contract.pt models/value_ids.contract.pt
  models/value_reference.contract.pt`, then
  `../../../.venv/Scripts/python.exe scripts/series_check.py compare
  target/sc_head.npz <file>.npz`. The cards are D5's (`D-loader.md`); the
  nets are the contract nets, through the `models` junction. A dump with
  other cards or nets fails the compare (state count, missing nets). Don't
  dump the baseline from the shared venv's module, as series_check's
  docstring shows: it is main's build, and compare checks only the old
  file's columns, so the branch's own (`next_draw_size`, `expr_*`) would go
  unchecked. Don't pass the tiny nets in `scripts/tests/data/contract`:
  they are pre-contract, and `stsnet.load` refuses them. Earlier runs on
  this branch report "4 contract nets" but never name them; name the nets
  you used in the commit.
- **H4:** `cargo run --release --example two_turn_phases 100 --check
  <file>`. Record it at `d9327a2` before the first edit, then compare later
  runs with `cmp`.
- **Machine:** other sessions and the job runner share this laptop. Run
  heavy work a few jobs at a time and cap threads (`-j 4` for cargo while
  other jobs run).
- **Commits:** one commit per build step, only once its check passes (global
  AGENTS.md: "Commit only finished work").

## Verification

- **Before step 1:** `cargo test --release` passes on `d9327a2`; the H4
  file and the series_check baseline are recorded (step 0).
- **Each step:** its findings' "Test first" fails before the edit and
  passes after, except a guard or control that its entry says passes
  today (for example A3, A5, E6, F3, G1-G4, and the invariants E2 and E3
  add; B1's `a_monsters_draw_hook_draws_for_the_player` fails only in a
  debug build): a guard must instead fail under the planted bug or
  mutation its entry gives, if any. The step's acceptance check passes,
  and `cargo test --release` or the Python suites the step touches pass.
- **End to end (step 36):**
  - `cargo test --release` passes, and so does a debug `cargo test -p
    sts-engine --test packs`.
  - H4 is byte-identical to step 0's file.
  - series_check compare passes against step 0's baseline.
  - These Python suites pass: `scripts/tests/test_warm_start.py`,
    `test_finetune_gen.py`, `test_contract.py`, `test_net.py`,
    `test_content_selfplay.py`, `test_registry.py`, `test_rust_net.py`,
    `test_bench.py`, `py/tests/test_sts.py` and
    `py/tests/test_content_pack.py`; also the ones the group checks run
    (`test_curve.py`, `test_gen_content.py`, `test_lookahead.py`,
    `test_branches.py`, `test_progress.py`, `test_puzzles.py`) and the
    other suites that replay records through step 2's check
    (`test_hp_loss.py`, `test_setups.py`, `test_survival_score.py`).
  - `git diff d9327a2 -- engine/tests/data` shows no change to `golden.txt`
    or `codec_golden.txt`, and none to `golden_proving.txt` beyond B2's
    named lines.

## Don't guard

- Don't add play-time checks for content the loader now refuses; the loader
  is the one gate. The exceptions are the engine-side guards an entry names
  (C1's copy guard, C2's hook-hit rule, D1's search bound, D5's saturating
  arithmetic, E3's and E5's decoder checks).
- Don't add work to official-content hot paths (card play, damage, hook
  dispatch, state hash): no new per-call allocation or scan. Each entry says
  how its fix stays off them.
- Don't weaken or delete an existing test to make a step pass. Don't lower a
  threshold in G1 or G4 without a decisions entry that says why.
- Don't re-record golden.txt, codec_golden.txt, or a Python pin that no
  entry names (see Scope, "Off limits").

## Full step order (the catalogue; the cut above decides what is built)

Run the steps in this order; each fixes the findings it names. "Details"
points to the step's files and acceptance check in the group file's "Build
step details" section. A test count a group file expects ("ends with 10
passed") assumes only that group's earlier steps. Under this order other
groups add tests to the same files first (D5 adds one to
`py/tests/test_content_pack.py` at step 17, before A2's at step 25), so
expect a larger count, with no failure. A few steps edit the same code,
and a later step merges into the code as the earlier one left it (never
reverting it):

- run()'s card-finished branch in `engine/src/state.rs`: steps 8, 9 and
  10 (step 5, C1, edits only `do_effect`'s ReplayCard arm);
- `do_effect`: steps 3 (the Draw arm), 5 (the ReplayCard arm) and 6 (a
  `from_hook` parameter, and the Damage and ScaledDamage arms);
- `condition_holds`: steps 8 (CardType) and 11 (CardsPlayedThisTurnBelow);
  `interpret_attack_damage` and `interpret_block`: steps 11 and 17;
- `grow_damage`: steps 17 (its `damage + k` made saturating) and 21;
- the pack parser in `engine/src/registry.rs` (`parse_card`, `parse_hook`,
  `card_effects`): steps 12, 14, 15, 16, 18, 19 and 20; step 16 drops only
  the GrowDamage clause of the `turn_end` check, and step 12's Draw check
  beside it stays;
- `try_decode` in `engine/src/codec.rs`: steps 13, 21 and 22;
- the expr form in `py/src/features.rs`'s `Encoder::effects`: steps 15
  (its comments) and 17 (its arithmetic);
- `registry.replay` in `scripts/registry.py`: steps 2 and 27. F1's
  `test_variant_records_replay` replays a record of an unfinished game,
  which step 2's check must accept;
- `engine/tests/packs.rs`'s imports: step 10 imports `Effect`, so step 16
  adds no second `use sts_engine::effects::Effect;`;
- the codec round trips: step 21 adds one to `check_invariants` in
  `engine/tests/common/mod.rs`, and step 34 changes only
  `engine/tests/codec.rs`, so nothing is merged or added twice.

0. **Baselines (no code), once, before any edit.** `cargo test --release`
   passes. Record H4 with `cargo run --release --example two_turn_phases
   100 --check target/h4_head.txt` (prints `wrote target/h4_head.txt`).
   Build this worktree's module with `bash scripts/dev_sts.sh` (the
   commits after `d9327a2` add only docs), then dump the series_check
   baseline `target/sc_head.npz` as "How to build and check" says; it
   prints `target/sc_head.npz: N states, 3 nets, module ...` with a path
   under `target/pyroot`. Never re-record or overwrite these two files:
   every later H4 `cmp` and series_check `compare` uses them, also where a
   group file says to record a baseline before its own edits or names
   another path for one (`B-chance.md` step B-0; `C-hooks.md` step 0,
   which also dumps from the shared `.venv` module; `D-loader.md` "Build
   step details"; `E-variants.md` step 1).
1. **A1.** First the parts that don't need the owner: `widen` takes named
   row kinds and never drops one, and `finetune.py` refuses a saved layout
   that differs from its data's. Then the one line that names the kinds,
   after owner decision 1 (stop point). Details: `A-training.md` step A-1.
   Until that line is in, the layout guard makes every warm fine-tune of a
   `['triggered']` parent raise (`test_warm_start.py::test_finetune_tiny`,
   `test_curve.py::test_curve_quick`). So the step's checks pass only once
   that line is in; commit the step then, not before.
2. **Outcome check in `registry.replay`** (owner decision 2, option (a);
   before B1 and B2 change generated play). Described just below this list.
3. **B1 parts 1-3:** draws add up; the monster-move assert; a monster's
   Draw. Details: `B-chance.md` step B-1.
4. **B2:** keep a reaction set during a monster's own move. Details:
   `B-chance.md` step B-4.
5. **C1:** copies are never replayed. Details: `C-hooks.md` step 1.
6. **C2:** a hook's hits fire no OwnerAttacked hooks. Details:
   `C-hooks.md` step 2.
7. **D1:** bound picks past the node cap. Details: `D-loader.md` step 1.
8. **E1 + E2:** read the card in play again after the hooks; drop variants
   when a card leaves play. Details: `E-variants.md` step 1.
9. **B1 part 4:** an after-card hook's draw is made before the card reaches
   its pile. Merge into step 8's code. Details: `B-chance.md` step B-2.
10. **C3:** hook AddCard, ScaledDamage and GrowDamage scale with stacks.
    Skip its stale-card re-read if step 8 already made it. Details:
    `C-hooks.md` step 3.
11. **C4 + C5.** Details: `C-hooks.md` step 4.
12. **B1 part 5:** packs refuse Draw at turn end. Details: `B-chance.md`
    step B-3.
13. **B3:** counted floater entries. Details: `B-chance.md` step B-5.
14. **D2 + D6:** refuse costs play can't pay, and official power names.
    Details: `D-loader.md` step 2.
15. **D3 (a):** ScaledDamage shape rules at load. Details: `D-loader.md`
    step 3.
16. **D7:** refuse GrowDamage on pack cards. Details: `D-loader.md` step 4.
17. **D5:** saturating damage, block and replacement arithmetic; also make
    `grow_damage`'s `damage + k` saturating (follow-up 5). Details:
    `D-loader.md` step 5.
18. **D4 step 1:** checked number conversions and the 255-effect cap.
    Details: `D-loader.md` step 6.
19. **D4 step 2:** lists and flags must have the right JSON type. Details:
    `D-loader.md` step 7.
20. **D4 step 3:** unknown keys refused inside structural objects. Every
    pack in `data/` must still load: `gen_powers_pack.json` carries the
    generator's metadata keys (budget, seed, gain, split, power,
    value_per_energy, keys, lifetime). Details: `D-loader.md` step 8.
21. **E3:** the decoder validates before it interns; a full variant table
    stops play. Merge with step 17's `grow_damage` edit (keep its
    saturating `damage + k`). Details: `E-variants.md` step 2.
22. **E5:** the tag-8 decoder refuses picks the engine never makes.
    Details: `E-variants.md` step 3.
23. **E4:** the rules fingerprint hashes registry.rs (after the manager's
    call). Details: `E-variants.md` step 4.
24. **E6.** Details: `E-variants.md` step 5.
25. **A2.** Details: `A-training.md` step A-2.
26. **A3, A4, A5:** docs and a threshold tripwire. Details:
    `A-training.md` step A-3.
27. **F1,** after building the module. Details: `F-tooling.md` steps 0 and
    F1.
28. **F2.** Details: `F-tooling.md` step F2.
29. **F3.** Details: `F-tooling.md` step F3.
30. **F4.** Details: `F-tooling.md` step F4.
31. **G1.** Details: `G-tests.md` step 1.
32. **G2.** Details: `G-tests.md` step 2.
33. **G3.** Details: `G-tests.md` step 3.
34. **G4.** Its round trips go in `engine/tests/codec.rs`, beside the one
    step 21 put in `check_invariants`. Details: `G-tests.md` step 4.
35. **H1,** after owner decision 3. See H1 below.
36. **Whole-spec check:** Verification's end-to-end list, against step 0's
    baselines. Details: `B-chance.md` step B-6, `C-hooks.md` step 5,
    `D-loader.md` "Final check after the last step", `E-variants.md`
    "Final check" and `G-tests.md` step 5. The docs/decisions.md lines
    they ask for (C's rules and open items; E's batch, including that the
    fingerprint now hashes registry.rs; G2-G4) go into the one entry for
    this spec that step 7 (D1) starts at the end of the file, not into new
    entries. When done, that entry holds every rule under "Taken in this
    spec".

Optional, after step 36: D3 (b) (`D-loader.md` step 9), then the items in
`K-cleanup.md`.

**Step 2 in detail** (no group file covers it):

- In `scripts/registry.py`, `replay(game)` steps through `game["actions"]`
  and then copies `score`, `won`, `hp_start` and `hp_end` from
  `game["outcome"]` into its result without checking them. After the loop,
  compare the final combat `c` with `outcome = game["outcome"]` and raise
  `ValueError` naming the game (encounter, seed) when any of these differ:
  - `c.won()` and `outcome["won"]`, and `c.score()` and `outcome["score"]`
    (exact: both are `CombatState::score()` of the same final state);
  - `c.turn()` and `outcome["turns"]`, and `c.player_hp()` and
    `outcome["hp_end"]`. On a loss, won and score are `False` and `0.0`
    whatever happened, so only these two catch a replay that diverged into
    another loss.
- Don't require `c.is_over()`. `runner::play_from` stops a normal-mode
  combat still running after `PLAY_TURN_LIMIT` (100) turns and records it
  lost (score 0, `turns` 101; decisions "Play turn limit"), so its replay
  ends with `c.is_over()` false, and the main checkout's datasets hold such
  games (`"turns": 101` in at least 20 of them). F1's
  `test_variant_records_replay` (step 27) also replays a record of a game
  stopped after five actions, whose outcome fields are that state's.
- `hp_end` is safe to compare: it is the final state's HP (`play_from`
  reads `s.player.hp`), and the end-of-combat heal is applied inside the
  state before it ends (`engine/src/state.rs:811-812`; none in no-death
  mode), so the replayed state holds the same value. Only the labels take
  the heal back out (`selfplay.label_heal`).
- Test first: `scripts/tests/test_registry.py::test_replay_checks_outcome`
  records official games with `sts.run(..., record=True)` and
  `registry.records` and replays each without error: a normal game; a
  no-death game (`no_death=True`, and `{"no_death": True}` as `records`'
  config); a branch game (a `forced` prefix, then `branch_at` set on the
  record); a turn-limit game, for example
  `("jaw_worm", ["Defend"] * 10, 1, 30000)` played by
  `sts.run("greedy", ...)` (it never attacks, so play stops at turn 101).
  Then it flips the normal game's `outcome["won"]` and expects
  `ValueError`. It fails today at that last part, because `replay` copies
  the outcome.
- Then replay real records: the first 20 games of each dataset under the
  main checkout's `datasets/` whose manifest has no `content_hash` (read
  only: `registry.iter_games(ds, root="../../..")`). None may raise: after
  landing, every cache rebuild runs this check, so a false alarm stops
  jobs. A mismatch there is a finding (the engine already replays that
  dataset differently): stop and report it instead of loosening the check.
- Acceptance: `scripts/tests/test_registry.py` prints an `ok` line per
  test and ends with `11 passed`; `scripts/tests/test_branches.py`,
  `test_hp_loss.py`, `test_setups.py`, `test_survival_score.py` and
  `test_contract.py` (they replay records through `registry.replay`) pass;
  the dataset replay above raises nothing. No Rust file changes, so no
  rebuild.

## Build plan

- **Mode:** forks, one per step (the `/build` skill), run one at a time in
  the order above.
- **Model:** the current one.
- **Stop points:** step 1's kinds line (owner decision 1); step 2 and
  everything that changes generated play (owner decision 2); step 23 (the
  manager's E4 call); step 35 (owner decision 3).
- **Long runs:** none over about 10 minutes. The full `cargo test --release`
  and the series_check dumps take a few minutes each.

## H. Docs and conventions

### H1. An unconfirmed draft spec was committed, and the branch note says it wasn't

- **Severity:** low · **Reach:** docs and process · **New on this branch:** yes · **Review:** cut by the 15 cap
- **Where:** `docs/specs/runtime-registry.md:1` (added in commit `1a51035`); `docs/engine-next.md:16-17`

**What goes wrong.** The file's title is `# Runtime registry (rules-engine spec 10) — DRAFT, not confirmed`, and lines 6-9 say it is "left for the owner" because it reopens two decisions that are expensive to reverse (the static Rust tables and the state representation). It entered history in `1a51035` ("Spec 8 review fixes and spec 10 stage 1"), whose `git add -A engine py scripts solvedb docs README.md` swept the untracked draft into an implementation commit; the commit message doesn't mention it, and it is not in `docs/specs/queue.md`. Twenty minutes later `cfeb931` wrote in `docs/engine-next.md` that the draft is "uncommitted, holds the owner's questions", which is now false. The owner's global working rule (their global AGENTS.md) is: "Commit only finished work: research once it's done, a spec once I confirm it, a step once you're sure it meets its goal. Unsure? Leave it uncommitted for the next step, or until a commit is required." Landing the branch with `git merge --ff-only engine-next` would put an unconfirmed spec, whose stage-1 text is already stale, beside the confirmed specs in main's `docs/specs/`.

**Fix.** The owner's call, since the draft holds the owner's open questions. Two options:
- (a) Keep the file, mark it the way main's two deliberate drafts are marked (`generated-cards.md`, `rules-engine-upgrade.md`: "DRAFT, not queued"), and correct `docs/engine-next.md:16-17` to say it is committed as a draft. Smallest change.
- (b) Remove it from the branch with `git rm` in a new commit (history keeps it), and keep it untracked until the owner confirms it.

Recommendation: (a). Either way, correct `docs/engine-next.md`.

**Test first.** None (docs). Check: `git log --oneline -- docs/specs/runtime-registry.md` and `docs/engine-next.md` tell the same story.

**Must stay unchanged.** Everything else.

## Follow-ups found while writing this spec (not verified)

These came up while the group entries were written and checked. None was
verified the way the findings were. Each needs its own check before anyone
fixes it, and none but follow-up 5 (build step 17 takes it) is part of
this spec's build.

1. **A hook's hit made while a tagged card is in play counts as coming from
   that card** (C5's open case). For example, a pack
   `CardPlayed { by: Owner }` → Damage hook that fires during a Shiv play
   gets Accuracy's bonus, or a monster's CardInPlayTagged DamageTaken
   bonus. `data/bench/gen_powers_pack.json` has 3 such hooks. Accuracy is
   proving content, so the training pools don't pair them today. Suggested
   fix, after C2: `attack` passes a `from_hook` flag to a private damage
   helper, and CardInPlayTagged also requires that the hit isn't a hook's.
   The public `attack_damage(src, dst, base)` keeps its signature.
2. **A no-death OwnerLostHp self-damage loop.** `take_damage`
   (`engine/src/state.rs:1486-1492`) computes `lost` before the HP floor,
   so it reports HP lost even at the no-death floor. An OwnerLostHp hook
   that damages its own owner then recurses once per HP point, and in
   no-death mode it never stops (about 16,000 levels deep even before the
   floor). Computing `lost` after the floor, as `lose_hp` does, plays the
   same for official content but doesn't bound the depth on its own. A real
   fix needs a rule, for example that a hook's hit doesn't fire its own
   power's OwnerLostHp hooks; that is the manager's call. Only hand-written
   packs reach it: `scripts/gen_content.py` refuses an OwnerLostHp hook with
   a self HP loss, but the loader accepts one.
3. **`Effect::scaled`'s Draw arm** (`n * k as u8`) wraps for negative or
   large stacks in the features. Clamp it the way C3 clamps the new AddCard
   arm. Nothing official changes.
4. **`cards_played_this_turn += 1`** (`engine/src/state.rs:604` and `716`)
   can overflow a u8 in a debug build if one play gets about 250 replays.
   `saturating_add` costs nothing and changes no official play.
5. **`grow_damage`'s `damage + k` is i16 arithmetic.** Extreme pack values,
   or a crafted decoded variant near `i16::MAX`, overflow it: a panic in
   debug builds, a silent wrap in release. Build step 17 makes it
   saturating.
6. **A hook that shrinks a grown card back to its base value files it as a
   variant** (`Rampage{damage=8/combat}`). That is a different card id from
   the base Rampage, although the two play the same, so equal positions can
   still differ by id. E1's second test expects today's behaviour. If the
   manager decides `grow_damage` should map "damage equals the base's
   damage" back to the base card, that test's expected id changes from 144
   to plain Rampage.
7. **`fetch` and `positions`** (`py/src/lib.rs`) still call
   `codec::decode`, which panics. After E3, a valid row that names an unseen
   variant while the variant table is full becomes a `PanicException`
   instead of a Python error. Optional: use `try_decode` and raise
   `ValueError`.
8. **`scripts/tests/test_finetune_gen.py`, run directly, never runs
   `test_hp_weight_targets`.** The file's `if __name__ == "__main__"` block
   (lines 122-126) comes before that test's definition (line 129), so the
   test runs only under pytest. Move the block to the end. This is older
   than the branch.
9. **B1 part 5 refuses only the direct turn-end Draw routes.** The indirect
   route described in B1's entry stays open, documented as packs only.
   Closing it needs an end-of-turn stop (a new Stage).
10. **Game-order assumptions.** Two fixes rely on the game's action order as
    recalled from the decompiled source, and nobody re-checked it:
    - B1 part 4: a CardPlayed draw comes before the card reaches its pile;
    - B2: the reaction's SetMoveAction runs after the move's own.

    The project's own note agrees for B2.

## Appendix X. Checked and refuted: don't redo these

A verifier checked each of these against the code and refuted it. They are listed so a builder doesn't spend time on them.

- **OwnerPlaysCard skips replayed copies** (review id v25). This is the trigger's documented meaning: `engine/src/hooks.rs:51-53` ("Not for a replayed copy (Burst)"), `engine/src/state.rs:644-646`, and `docs/decisions.md:1944-1947`, which says the game fires `onUseCard` for copies but Burst ignores them. A pack that wants a copy-aware trigger has `CardPlayed { by: Owner }`, which fires for copies (the trigger Rage uses). Only the phrase "no other reader yet" in decisions.md is stale; touching it is optional.
- **`scripts/dev_sts.sh` deletes `target/pyroot` before building** (review id v26). The script runs under Git Bash, whose `rm` (Cygwin) removes a loaded `.pyd` by renaming it into the recycle bin and returns success, so the build is not aborted. The verifier tested this with a live Python process holding a `.pyd` from a copy of `pyroot`.
- **The heuristic counts an X-cost card's damage at a full turn's energy but charges it 0 energy** (review id sw_core_2). The confirmed spec 2 prescribes both halves: the card's cost stays 0 for every cost reader, and the heuristic takes X as 3 for Whirlwind (`bf7422f:docs/specs/amount-expressions.md`; `docs/decisions.md:1758`; `engine/src/cards.rs:215`; `docs/extending.md:198-201`). Whirlwind is proving content, outside every training and eval pool.
- The rejected cleanup ideas (review ids c05, c09, c10, c20, c25) are listed at the end of Appendix K.
