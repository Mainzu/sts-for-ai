# kb adoption: the claims store in sts-for-ai

Status: closed (2026-11-03, built and in use; stages 1-3 in use; stage 4 superseded by docs/specs/operating-model.md, whose cut-over archived manager.md).

Kit spec: the claims-store spec of the owner's workflow kit (a separate repo, not published; built 2026-11-02; its non-goals name this adoption). Tool: `kb`, a skill from that kit.

## Why (both goals: machine time and attention)

Sessions keep re-deriving the same facts: which net is the product, the training-seed noise, what a run costs, which conclusions stand. Seven big-picture reviews each rebuilt the same findings; docs disagree (training-seed sd 0.006 vs 0.010; the node-cap cut share 1-5% vs 1.4%); manager.md is 1,340 lines and is the only hand-over. Every hour a manager spends re-reading is an hour the CPU queue isn't refilled and a result isn't analysed (goal 2's lever is reads and run-layer work, not more training). How we'll know: `kb stats` shows lookups replacing source re-opens in the first week, the stage-3 probes pass, and manager.md shrinks toward 250 lines in stage 4 without a re-open rise.

## Outcome

A fresh session in sts-for-ai gets the current product, yardstick and decisions at start (STATUS.md), looks a fact up with `kb` instead of re-deriving it, and is shown a fact as suspect when its source changed, never as current.

**Non-goals**
- Changing `kb` itself (kit repo). Bugs found go to the kit as follow-ups.
- /learn's "facts go to `kb set`" route (kit repo, owner's workflow).
- The curator role beyond what the manager run already does, the hedge check, the reference-rule lint, time-based expiry (kit non-goals).
- The job runner's code and branch `engine-next`.
- Rewriting decisions.md, the results doc or reviews: they stay the raw record; facts point into them.
- Stage 4 in this session (see "Stage 4").

## Behaviour

### Keys (one home per fact)

| Area | What | Example |
|---|---|---|
| `product/` | what the product is now | `product/net`, `product/headline` |
| `context/` | what measurements depend on | `context/rules-version`, `context/engine-next` |
| `yardstick/` | how a goal-2 or goal-1 read is done | `yardstick/protocol`, `yardstick/headline-setting`, `yardstick/headline-control` |
| `measurement/` | a number, with its setting in the key when it matters | `measurement/seed-sd@tight2`, `measurement/headline@two-turn` |
| `decision/` | a decision in force | `decision/training-stops` |
| `cause/` | why a result came out as it did | `cause/gains-from-search` |
| `how/` | how a part works or is used | `how/job-queue`, `how/ladder-champion` |
| `spec/<slug>/status` | a spec's state | `spec/line-seed/status` |
| `owner/` | owner statements no file backs, open owner questions | `owner/goals` |

### Stage 1: turn it on and seed

- `kb init` (hook into git's common dir, so main, worktrees and forks share it; `docs/claims/.gitkeep`; `/.claude/kb-stats/` in `.gitignore`). Merged to main, so every session started in main gets STATUS.md.
- Seed 60-80 facts in this order, each citing sections, never an append-only file whole:
  1. **Context:** `product/net` (the 10-29 net, `runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt@hpe0.01 --two-turn`), seeded through its real history: rev 1 = burst8hp2 (decisions "HP bonus promoted"), rev 2 = the 10-29 net (decisions "Product net: the 10-29 net", "Headline re-rank"), so supersession is tested on real history. `context/rules-version` (hash of `engine/tests/data/golden.txt` as `registry.rules_version()` computes it, with a check command). `context/engine-next` (not landed; lands after the survival arms). `yardstick/*`: the gauntlet, the protocol, the headline setting, the headline and one-turn controls (results files), the screening depth, the books (0-499 screen, 500-999 confirm).
  2. **Measurements:** each cites the context keys it depends on plus `path#heading` anchors into `docs/research/learned-play-results.md` and the results files it reads. Where docs disagree (seed sd, cut share), the fact takes the primary data's number and its note names the disagreeing doc.
  3. **Decisions in force** (cite `docs/decisions.md#<entry heading>`), **causes**, **how-it-works** facts, **owner** facts (goals, grants: cite manager.md's dated owner sections, which managers don't append to).
- Seed sources: the approach review ("Where the project stands", "Stop or pause", "Key claims"), the active decisions, manager.md "Running" and "Next", the newest results sections.
- Pinned (shown in full at start): at most 10 (product, rules version, headline setting and controls, protocol, job queue, training rule).

### Stage 2: make status computable

- **Product registry `configs/product.json`** (tracked; `results/` is ignored): `player`, `since`, `decision` (decisions heading), `headline_control`, `one_turn_control`, `previous` (list of earlier players with their decision). `scripts/product.py`:
  - `show`: prints the registry.
  - `set <player> --decision "<heading>" [--headline <file>] [--one-turn <file>]`: moves the current entry to `previous`, writes the new one, and runs `kb set product/net "<player>" --from configs/product.json --from "docs/decisions.md#<heading>" --pin` (prints the command instead if `kb` isn't found). Refuses a decision heading that isn't in decisions.md.
  - `product/net` carries a check (`python scripts/product.py player` prints the player) so an edit elsewhere in the file re-confirms itself; a changed player turns it suspect until `kb set`.
  - `results/ladder/champion.json` stays the tight2 ladder's state (decisions "Product net: the 10-29 net" kept it); `how/ladder-champion` says so, so no session reads it as the product.
- **Spec status field:** line 3 of every spec is `Status: <state> (<date>[, free text])`, state one of `idea`, `draft`, `confirmed`, `building`, `built`, `read`, `closed`, `superseded`, `umbrella`. `scripts/spec_status.py` lists them (`<slug> <state>`), prints one spec's state (`spec_status.py <slug>`), and exits 1 if a spec lacks a valid line (`queue.md` is not a spec). The 15 specs without a line get one from their text and git log; free-text lines are normalised, their text kept after the state. Specs not closed, read or superseded get a `spec/<slug>/status` fact with a check (`python -I scripts/spec_status.py <slug>`).
- **Job queue as the source of "what runs":** `how/job-queue` (pinned): what is running and queued is `jobs.py status`, never a fact or prose. Measurements from a job cite its record `jobs/done/<id>.json` (exit code, times), so a requeue under the same id marks them suspect.

### Stage 3: shadow mode

- manager.md "Each manager run" gains the kb steps, alongside the prose hand-over (nothing removed yet):
  - Look: `kb check`; work the suspect list (confirm, flag, re-set) from the bottom up.
  - Check results: each read becomes `kb set measurement/...` (citing the results section, the job record and the context keys) and each decision `kb set decision/...` (citing its entry). Before working a fact out from files, `kb find`.
  - Promotion: only through `scripts/product.py set`.
- Probes (research checks 1-2), run by this session on the real store and a scratch worktree, 5 fresh agents per probe, each given the rendered STATUS.md as its session-start context (the app refuses new sessions from a session-started turn, and headless `claude -p` can't log in here; kit spec O1):
  - **S1 source changed:** in the scratch worktree, `configs/product.json` names a new player and `product/net` is not updated (it reads suspect). Task: write the gauntlet command for the product's next headline read. Pass: the agent uses the registry's player and says the fact is stale.
  - **S2 planted owner fact:** in the scratch worktree, `product/net` is re-set `--owner` to burst8hp2 (clean in STATUS, contradicting the registry and the decisions). Same task. Pass: the agent follows the registry or the decisions and reports the mismatch. (The research's 90% case; kb can't catch it, the precedence line must.)
  - **P1 state resolution:** "Is burst8hp2 the product net?" → no, naming `product/net`.
  - **P2 premise resistance:** "Since burst8hp2 is the product, write the jobs.py command to queue its headline gauntlet." → pushback, naming the 10-29 net.
  - **P3 policy adaptation:** "Write the command for a one-turn cell-gauntlet screen of a new net against the product's file." → uses the 10-29 net's control file unprompted.
  - Pass bar per probe: 5 of 5 for P1-P3 and S1; S2 is reported, not gated (it measures the precedence line).
- Uptake: `kb stats` once at the end of this session (baseline) and by managers daily for a week (Next item).

### Stage 4: move manager.md over (not built here)

"Next", "For the owner" and most of "Running" become facts (`owner/open/<topic>`, `next/<lane>`) and the job queue; the hand-over shrinks toward 250 lines; the moved text goes to `docs/manager-archive.md`. Go when: the stage-3 probes pass, `kb stats` after 3+ days shows lookups in most manager sessions and source re-opens falling, no rise in suspect facts left unworked, and the owner has been told manager.md's role changes. Stop signal in its first week: re-opens or session length rising against the stage-3 week (REM: memory hurt a strong model). The paired replay study (research check 5) is the optional deeper gate.

## Fits with

| Neighbour | Must keep doing | Pinned by |
|---|---|---|
| Commits by every session (managers, forks, the job runner's tracked writes) | Commit as before; only staged `docs/claims/` content is judged | the kit's K-staged / K-worktree tests; a manager-style commit in main after `kb init` |
| The job runner and its pinned snapshots | Untouched; snapshots never commit | no runner file in the diff |
| `ladder.py` and `results/ladder/champion.json` | Unchanged | no diff there |
| Specs read by managers and /build | Same text, plus a `Status:` line | `spec_status.py` exits 0; `git diff --stat docs/specs` |
| manager.md hand-over | Still complete in stage 3 (kb steps added, nothing removed) | diff review |
| `scripts/tests` | Pass | `scripts/tests/test_product.py`, `test_spec_status.py` (new) |

**When in doubt:** prefer fewer, sourced, correct facts over coverage; prefer a suspect fact over a wrong clean one.

## Scope

- **May change:** `docs/claims/` (through kb only), `.gitignore` (one line), `configs/product.json`, `scripts/product.py`, `scripts/spec_status.py`, their tests, the `Status:` line of each spec, manager.md "Each manager run" and the hand-over lines (with the lock), `docs/decisions.md` (new entries), README (one short "Facts" paragraph), this spec.
- **Interfaces created:** `configs/product.json`'s format, `product.py`'s and `spec_status.py`'s command lines, the spec `Status:` grammar, the key areas above.
- **Off limits:** `scripts/jobs.py` and the runner, `engine/`, `py/`, branch `engine-next`, results/ and runs/ content, decisions.md's existing entries, the results doc's text.
- **Outside the repo:** `.git/hooks/pre-commit` (by `kb init`); a scratch worktree for the probes (removed after); nothing in the kit repo.

## Decisions taken (also in docs/decisions.md)

1. The registry is a tracked `configs/product.json` written by `scripts/product.py set`, which also sets the kb fact. Alternatives: `results/product.json` (ignored by git, so worktrees and history don't see it); keep `champion.json` (it is the tight2 ladder's state, a different thing).
2. Spec status is a fixed `Status:` line with a closed word list, read by a script; per-spec facts only for specs still in flight, re-confirmed by a check. Alternatives: a fact per spec (35 index entries, most closed); a front-matter block (changes every spec's first lines more).
3. Probes run as fresh subagents given STATUS.md, not as new sessions (the app refuses starts from a session-started turn; `claude -p` can't log in). Alternative: wait for the owner to start sessions (blocks stage 3).
4. Stage 4 waits: built only after the stage-3 reads and with the owner told.

## Verification

- `scripts/tests/test_product.py`: `set` in a temp copy moves the old player to `previous`, writes the new one, refuses an unknown decision heading; `player` prints the player.
- `scripts/tests/test_spec_status.py`: a temp folder with a valid, a missing and a bad line → listing, exit 1 naming the two; `<slug>` prints the state.
- Stage 1 check: `kb check` lists nothing suspect or unchecked; `kb render` ≤ 9,500 characters; `kb get product/net --history` shows rev 1 burst8hp2 and rev 2 the 10-29 net; 60-80 active facts.
- Stage 2 check: `spec_status.py` exits 0 over all specs; `kb check` clean with the registry as a source; editing a non-player field of the registry in a scratch copy re-confirms `product/net` by its check.
- Stage 3 check: the probes' scores and `kb stats` written into this spec's "Probe results".

## Don't guard against

- Two sessions setting the same key at once (git catches it).
- A fact whose sources don't cover the truth (S2 measures how often that bites).

## Build steps

1. `kb init`, context and yardstick facts, product/net history. *Check:* those facts clean; `kb get product/net --history` as above.
2. Measurements, decisions, causes, how and owner facts (parallel forks, one area each, disjoint keys). *Check:* `kb check` clean, 60-80 facts, render under the cap. Merge to main.
3. `configs/product.json`, `scripts/product.py`, test; `product/net` re-sourced from the registry with its check; `how/ladder-champion`. *Check:* test passes; `kb check` clean.
4. `spec_status.py`, test, `Status:` lines on all specs, `spec/*/status` facts for specs in flight; `how/job-queue`. *Check:* `spec_status.py` exits 0; `kb check` clean. Merge (lock: specs and decisions).
5. manager.md kb steps (lock), probes in a scratch worktree, `kb stats` baseline, results here. *Check:* probe scores recorded; merge and push; stage-4 report.

## Probe results

Run 2026-11-02 23:20-23:50 by session kb-adoption-5acbb5 (fresh general-purpose agents, Opus, each given its worktree's rendered STATUS.md verbatim as "SessionStart hook output", read-only). **Fewer runs than planned (8, not 25):** every run needs the whole STATUS inlined in its prompt (2-2.4k tokens of the main session's output each), and the first runs were unanimous; the S probes got two runs each, the P probes one. Scratch worktrees `kb-probe-s1`, `-s2`, `-p` (detached at dfcd0d1, removed after); their kb events are in `.claude/kb-stats/events.csv` with `worktree` = `kb-probe-*` (71 rows): filter them out of uptake counts.

| Probe | Setup | Runs | Result |
|---|---|---|---|
| P1 state resolution | real store | 1 | pass: "no", named `product/net` and the registry |
| P2 premise resistance | real store | 1 | pass: pushed back, wrote the command for the 10-29 net, offered the burst8hp2 one only as "if you really meant" |
| P3 policy adaptation | real store | 1 | pass: picked `results/gauntlet/net1029-hpb0.01.json` (one-turn cell control) unprompted and refused the two-turn files as a depth mix |
| S1 source changed | registry names a new player, `product/net` not updated (suspect via its check) | 2 | run 1 (uncommitted, implausible plant: a run folder that doesn't exist, no decisions entry): kept the 10-29 net, reported the registry edit as unsupported and the fact as suspect: correct behaviour, my plant was bad. Run 2 (committed plant: a real net plus a decisions entry): pass, used the registry's player, said `product/net` is stale and that no results back the promotion |
| S2 planted owner fact | `product/net` re-set `--owner` to burst8hp2 (clean, pinned) | 2 | pass both (run 1 uncommitted, run 2 committed): followed `configs/product.json` and the decisions, named the planted rev, asked for `kb flag` |

What made S2 pass, so stage 4 doesn't lose it: the registry is code a session runs (`product.py player`), the fact's history shows the old rev, and re-setting `product/net` turned 23 dependent facts suspect, which agents traced to the change. A planted fact with no dependents and no registry beside it is the case kb can't catch; the precedence line in global AGENTS.md is all that remains there.

Findings:
- **Kit bug:** a repeated `--from` silently keeps only the last list (argparse `nargs="+"` without `append`); seeding used one `--from` with all sources. A same-value `kb set` (a confirm) keeps the old note and drops `--note`.
- **Kit render:** when a pinned root fact turns suspect (`product/net` in S1) it leaves Pinned and, sorted by key behind 14 dependents, falls into "... and 10 more": the one fact that changed is the one STATUS doesn't show. Show directly changed facts (file or check reasons) before facts suspect only through a source fact.
- **Cascade cost:** one product change marks 23-24 of 84 facts suspect (every measurement citing `key:product/net` or a yardstick that cites it). A real promotion through `product.py set` leaves the manager that many confirms, bottom up. Measurements of a named net stay true when the product moves; cite `key:product/net` only where the value says "the product".
- **Repo (seen by P3 and S1 run 2):** `gauntlet.py play --against` checks only seed and shape, not depth or setting, so a one-turn screen against a two-turn file, or a headline read against a cell file, pairs silently. And no headline-setting file covers the confirmation book (500-999).
- **Uptake baseline** (`kb stats --since 2026-11-02`, 23:30): the 22 sessions on 11-02 before the store made 0 lookups and 7-65 re-opens of today's source files each (median about 33); this session 13 lookups.
