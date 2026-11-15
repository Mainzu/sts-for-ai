# Operating rules (owner away)

Three roles run the project while the owner is away (spec
`docs/specs/operating-model.md`). Each reads this file at start; its own
duties are in its prompt (the steward's in
`~/.claude/scheduled-tasks/sts-steward/SKILL.md`, the others' in `docs/roles/`).
The owner adds ideas (an issue tracker, label `project:sts-for-ai`; reviewed
as usual) or discusses the approach with `/approach`, where a suggestion is
reviewed with them on the spot; the outcomes (`docs/direction.md`, backlog
entries, decisions marked "(owner, <date>)", not "(owner away)" bind the roles. Never ask the owner.

The "(owner)" sections are the owner's words; only the owner changes them.

## Goals (owner)

1. An AI that plays well on randomly generated content (cards, powers,
   enemies), with first-class support for custom content: a new character,
   a new mechanic, a new entity.
2. On that system, a Slay the Spire AI as dominant in its field as
   Stockfish is in chess.

Subgoals: add relics; widen the scope beyond combat toward the full game.

Finish Act 1 (essential): every official Act 1 monster and encounter, and
every Ironclad card, relic and potion an Act 1 run can meet, loads and
plays in the engine (`docs/INDEX.md` "Act 1 coverage" keeps the count).
A lane on it stays open until that holds. When it closes at a cap or end
date with Act 1 unfinished, the next free project slot reopens it with a
new cap; a missing building block is a reason to build the block, never
to close or skip the content.

Scope note: the out-of-combat parts (map, rewards, rest sites, shops,
events) are built as a headless rules simulator for training and testing,
like the combat engine: no playable front end, art or game text. Playing
the real game, if we get there, goes through a mod bridge to the owner's
own copy (since built: README, Real-game bridge).

## Standing grants (owner)

- **Decisions.** AGENTS.md's "ask before decisions that are expensive to
  reverse" now means: decide, record it in `docs/decisions.md` marked
  "(on the owner's behalf)" with the alternatives, prefer the reversible
  option, and list it in the daily digest. Spec confirmation is yours too.
- **Push.** Push finished commits on `main` to `origin` with a plain
  `git push`. Never force-push or rewrite history.
- **Disk.** When the disk runs low, delete only rebuildable files: caches, data a script regenerates,
  finished worktrees. Never `db/` databases, `models/`, `results/` or
  anything a commit references. Below 8 GB free, start no new run that
  writes much.
- Not granted: deleting non-rebuildable data, git history rewrites,
  spending money, system or security settings, anything outside this repo
  except `~/.claude` memory and the ideas issues (label
  `project:sts-for-ai`; adding and commenting is fine).

## Machine time is the bottleneck (owner)

CPU time is the scarce resource. The owner spends about half their
time waiting for training runs inside tests to finish. So:
- Keep the CPU busy with the most valuable run at all times. Have the
  next run ready before the current one ends.
- While a heavy run goes, do work that needs little CPU:
  specs, code, reviews, analysis of finished results, research, the
  next run's preparation. Hold back test suites that train nets until
  the CPU is free.
- Make runs cheaper: shrink slow tests (smaller fixtures, separate a fast
  suite from the slow one), take the exact-solver step out of training
  rounds (~70% of a round).
- Before a run, check it can decide something: training-seed luck has
  sd ~0.010 train / ~0.013 held-out on tight2. MDE = 2.8 x sd x sqrt(2/seeds), ~0.02-0.03 at 3 seeds, smaller
  only when arms share data (pairing corr 0.8-0.99 for data/rates arms).
  A run whose expected effect is below its MDE doesn't run.

## Training: when it runs and when it stops (owner)

Gauntlet gains come from search and the run layer; more of the same
training plateaued after one self-play round. So:
- A training job runs only when the net has something new to learn: a
  stronger teacher (games from the two-turn product), inputs it can't see
  today (a new layout, the survival histogram), or new content. Anything
  else doesn't get CPU. It is judged on the gauntlet protocol.
- It stops at the plateau. After each round, play its net on the one-turn
  cell gauntlet (500 sequences) and read it `--against` the file of the
  net from two rounds back with `--d1 4`: a pass (the two rounds gained
  more than about 2 HP) trains another round, a fail stops. Optional free
  pre-screen: if the new net changes far fewer picks on
  `data/bench/decisions.json` than round 0 -> 1 did, stop without
  playing (this signal can stop training, never promote a net). For
  cheap fine-tune bursts, look three rounds back with `--d1 6`.
- Goal 1 is the exception in kind, not in rule: how few games a net
  needs to adapt to new content is the goal-1 number, so there a curve of
  games against retention is worth measuring.

## Big-picture reviews (owner)

The owner wants data analysis, big-picture reviews and abstract thinking,
not only the next spec. So:
- **About every 3 days, and after any
  major result,** run the saved workflow `big-picture-review` (in
  `.claude/workflows/`, by name). It reads the data and docs through
  several lenses, synthesises, and has skeptics check the key claims.
  Write the outcome to `docs/research/big-picture-<date>.md` and re-rank
  `docs/backlog.md` from it. The newest such file outranks the backlog's
  order.
- **Before starting any spec,** say in one paragraph in the spec how it
  moves goal 1 or goal 2 and how we'll know; if you can't, don't build it.
- **A probe needs a trade-off.** For a spec that measures a choice (a
  probe or read comparing options), write down what each option can gain
  on the current setting. If one option can't gain anything there, the
  answer is already known: don't spec the probe. Record that, then spec
  what would give that option its value, or drop the question.
- **Idle thinking time is wasted capacity.** CPU-light thinking
  (analysis of existing data, prior-art research, design reviews,
  experiment design) can always run in parallel with a CPU-heavy run.

## Roles

| Role | Task | Cadence | Writes |
|---|---|---|---|
| Steward | `sts-steward` | Haiku; every 4 h at :20 | `jobs/health.json` (via `health.py`), `docs/filler.md`, `docs/digest/`, ideas triage lines in `docs/backlog.md`, results no lane filed |
| Navigator | launcher, `docs/roles/sts-navigator.md` | Opus at high effort; on the wakes it sets itself, the owner's wake, a lane worker's wake or stagnation, else every 72 h | `lane/<name>` facts, `jobs/lanes.json`, `docs/backlog.md` (ideas, ratings, ready charters), `jobs/navigator-wakes.json`, decisions, `cause/` and `decision/` facts, `docs/research/` |
| Lane worker | launcher, `docs/roles/sts-lanes.md` | Sonnet; on an event, else every 4 h while a lane is open; one at a time, at most 4 a day | its lane's branch and worktree, `lane/<name>/step`, `lane/<name>/checkpoint`, results docs, measurement facts, decisions; at its lane's close the close entries, `measurement/portfolio-<name>`, the next lane from a ready charter and `jobs/lanes.json`, or a navigator wake; a dead-man note in `docs/digest/` |
| Curator | `sts-curate` | Sonnet; daily at 11:40 | `docs/claims/` only, by `~/.claude/skills/curate/SKILL.md`: overdue suspect facts, duplicates, splits, long values; one area per run |

- Health comes first: a red blocker gates the navigator, and the steward
  fixes it before anything else.
- The steward never plans, picks research or touches charters. The
  launcher starts a dead job runner itself on its next tick
  (`scripts/roles.py`, `RESTARTS`); the steward restarts the launcher and
  anything the launcher left red (others note a dead one in
  `jobs/roles.log`, which the steward reads each run). The navigator
  never edits code; its job is new approaches and the ranking. A lane
  worker works only its claimed lane, and closes it.

## Where things live

- `docs/README.md`: the start page, pointing to where each kind of truth
  lives; `docs/INDEX.md`: every doc, each spec's state and Act 1's
  coverage, written by `scripts/docs_index.py` (AGENTS.md gotchas).
- `docs/direction.md`: goal weights, interests and things to avoid, written
  only from a reviewed discussion with the owner; it outranks every other
  ranking.
- Lane charters, split by writer:
  - `docs/lanes/<name>.md` (navigator): the full charter: goal, measure,
    stop rule, kind (`project` or `exploration`), CPU-hour cap, end date
    and on-close condition;
  - `lane/<name>` (navigator): a summary of 400 characters or less citing
    that file, written as `<goal and go rule>; kind: project; cap: 30
    cpu-h; end: <YYYY-MM-DD>; on-close: wake on go; charter:
    docs/lanes/<name>.md` (`health.py` reads `kind:`, `cap:` and `end:`;
    the closing lane worker reads `on-close:`); shares live only in
    `jobs/lanes.json`;
  - `lane/<name>/step` (lane worker): current step and next checkpoint;
    `done: <outcome>` when the stop rule or goal is reached;
  - `lane/<name>/checkpoint` (lane worker): `passed <name>` or `failed
    <name>`; kb's `at` dates it.
  Closing a lane (the lane worker) retires all three with the outcome and
  a "reopen if" condition.
- `docs/backlog.md` (navigator): open questions, and candidate lanes with
  source, mechanism, goal, a rating in words (likely, even, a long shot)
  with its evidence, CPU-hour estimate and cheapest probe; the top one or
  two carry a ready charter; the steward appends triaged ideas.
- `jobs/navigator-wakes.json` (gitignored): the navigator's wakes, each
  with its reason (`health.py navwake`); the owner adds one with
  `scripts/roles.py wake navigator "<note>"`, a lane worker at a close.
- `docs/filler.md` (steward): standing small jobs, including `test-full`.
- `jobs/health.json` (gitignored): `scripts/health.py`'s report; no commits.
- `docs/digest/<date>.md` (steward): the daily digest.
- Per-job read rules stay in each job's `note`. The lane that owns the job
  reads it; the steward only files values no lane filed.
- `jobs/locks/`, `jobs/wakes.json` and `jobs/roles.log` (gitignored):
  locks, the navigator's run record, and one line per role run (`<YYYY-MM-DD HH:MM> <role>
  <session id> <outcome>`), from which the digest counts sessions.

## Writing to main

- **Lane workers** work in their own worktree on branch `lane/<name>` (the
  /build way) and never edit the main checkout. To land: rebase the lane
  branch onto main in the worktree, take the `main-merge` lock, `git -C
  <main checkout> merge --ff-only lane/<name>`, `git push`, release. If the
  merge is refused (uncommitted files in main), release the lock and leave
  main untouched (no stash, no checkout); land at the next session.
  Main moves often, so merge right after the rebase; if the fast-forward
  is refused because main moved, rebase again and merge at once. A rebase
  rewrites the lane's commit hashes: once merged, update the hashes the
  lane's docs and facts name in one commit on main.
- **The steward and the navigator** edit only their own files in the main
  checkout, and commit each group of edits right away by explicit file
  paths (`git add -- <files> && git commit -m "..." -- <files>`), then a
  plain `git push`. Never leave edits uncommitted while doing something
  long: a lane's fast-forward merge refuses over them, and another role's
  commit of the same file would sweep them in. Shared append-only files
  (`docs/decisions.md`, results docs) and kb facts (`docs/claims/<key>.json`)
  are written the same way.
- No `pull --rebase`: only one machine pushes. A refused push is reported in
  the digest, never forced.
- **Queue adds from the main checkout** use `--pin $(git rev-parse HEAD)`,
  which avoids the dirty-tree refusal while a lane edits elsewhere. Lane
  workers add from their worktree after committing (pinned to their HEAD).
- **Swapping `sts`** in main: under the `main-merge` lock, by AGENTS.md's
  gotchas (`jobs.py impact sts` first, recorded in the commit; build first,
  swap last; install a snapshot's wheel when `jobs.py pins` shows one).

## Locks, claims and wakes

- A lock is `jobs/locks/<name>.json` with holder, session id, time and
  heartbeat. `python scripts/health.py lock take|beat|release <name>
  --holder <role> --session <id>`; `take` exits 1 and names the holder
  when held.
  - `main-merge`: held while merging into main or swapping `sts`.
  - `lane-<name>`: a lane worker's claim. Take it before working a lane;
    skip claimed lanes. Refresh the heartbeat at each commit or about every
    30 minutes.
- Any role breaks a lock (`take --break`) whose heartbeat is over 45
  minutes old and whose holder isn't running: `scripts/roles.py status`
  shows no running session of the holder's role other than yours, and its
  worktree has no commits or file changes in the last 30 minutes.
- **The role launcher** (`scripts/roles.py run`, `jobs/roles.pid`; decisions
  "Role launcher as built") starts the lane worker and the navigator
  as headless CLI sessions (`claude -p`, auto mode) on the events
  `health.json` lists under `wakes`: `wakes.lanes` (a lane's job ended, a
  lane with nothing queued, a failed `test-full`, a lane done or past its
  cap or end date) and `wakes.navigator` (the wakes in
  `jobs/navigator-wakes.json` that fired, stagnation); one event starts
  one session, and a 72-hour backstop starts the navigator. It resumes a
  role's previous session when its cache is warm and its context small
  (`scripts/roles.py` docstring). It holds the session limits, one session at a time
  (never a lane session beside the navigator) and time limits (lanes
  4 h, navigator 2 h). `roles.py chat navigator` opens the navigator's
  last session for the owner; no headless navigator starts meanwhile. Nothing starts
  while a blocker is red. `roles.py status` shows the
  sessions; their output is in `logs/roles/`, records in `jobs/roles/`.
- No role starts another. The steward stays an app task (only app
  sessions have push notifications).

## Machine limits

- No usable GPU (torch runs on CPU).
- At most two CPU-heavy jobs at once; cap their threads. Check CPU and
  free memory before starting one. Below-normal priority doesn't help.
  Size memory to what's free, avoid paging.
- **Memory is the binding limit.** The runner admits a job only if
  `mem_gb` + 1 <= free. Peaks: two-turn at 2 threads ~3.0-3.5 GB, at 3
  threads 3.2-4.7 GB; one turn ~1 GB; a 6-thread training arm 3.8-4.3 GB.
  Set `mem_gb` from these (or from `peak_gb` in `jobs.py status`).
- pytest is not installed in `.venv`. Run tests with the system interpreter
  over the venv's packages: `PYTHONPATH=.venv/Lib/site-packages
  <system python> -m pytest -q -p no:cacheprovider
  scripts/tests/<file>` (Bash). With a private wheel first on the path
  (`<pyroot>;.venv/Lib/site-packages`), write both as full Windows paths
  (`C:/...`): Git Bash garbles relative or `/c/` entries. A worktree lacks
  main's untracked data (`models/`, `runs/`); link it in with a junction
  for tests that need it, and remove only the link. The full run is the queue job
  `test-full` (`docs/filler.md`). Suites that train nets wait until the CPU
  is free. `test_jobs.py` is flaky on a free-memory assertion.
- **series_speed** compares two folders that each hold `bench.exe` and
  `search_speed.exe`, not installed packages. For each commit, check it out
  in a temporary worktree (`git worktree add --detach target/<dir>/src-<v>
  <commit>`), run `cargo build --release -p sts-engine --example bench
  --example search_speed --target-dir ../build-<v>`, copy the two programs
  into `target/<dir>/<v>`, then `git worktree remove --force` the checkout.
  Queue the comparison with `jobs.py add`; delete the folders once the job
  is read.

## Job queue

Long runs go through the queue, not by hand (README "Job queue"):
- `jobs.py add --threads N --mem-gb G --estimate-min M --lane <lane> --note
  "<read rule>" -- <cmd>`; the note says how to read the result and what a
  pass or a fail changes. Keep the lane's next job queued before the
  current one ends.
- Order: `first <id>` starts a job next. Lanes and shares are in
  `jobs/lanes.json` (the navigator's), plus `main` 10 and `filler` 0.
- Conditions instead of `bash -c "A && B"`: `--after a,b`, `--if-passed
  a,b` (with `--check "cmd"` on the job whose result decides), `--on-fail
  park|cancel`; `set <id>` changes a pending job, `unpark <id>` and
  `verdict <id> pass|fail` handle a parked chain; `estimate <id> <min>`
  re-estimates a pending or running job (the steward's overrun fix).
- Pinning: `add` pins to HEAD by default and refuses with uncommitted
  scripts, engine or configs (commit, or `--unpinned` for jobs that write
  tracked files or new files in `data/`). Before a swap, merge or landing,
  run `jobs.py impact sts|scripts` and record the result. `pins` lists
  snapshots; only `unpin` or the runner's 24 h sweep removes one.
- Runner restart (the launcher's tick, else the steward), when `jobs/runner.pid` names a dead
  process: PowerShell `Start-Process .venv\Scripts\python.exe -ArgumentList
  '-u','scripts/jobs.py','run' -WindowStyle Hidden -RedirectStandardOutput
  logs/jobs/runner.out` in the main checkout. It adopts running jobs and
  still records their exit codes. Exactly one runner.
- Launcher restart (steward only), when `jobs/roles.pid` names a dead
  process: `Start-Process .venv\Scripts\python.exe -ArgumentList
  '-u','scripts/roles.py','run' -WindowStyle Hidden -RedirectStandardOutput
  logs/jobs/launcher.out` in the main checkout. Exactly one launcher.
- Filler jobs (lane `filler`) must be `--resumable` or estimated at 20
  minutes or less; they start only when nothing else does.

## Reading results

- Read anything finished, and be suspicious. A result much better or worse
  than the last, a check that passes at exactly its bar, a number that
  disagrees with an earlier measurement, or a run far faster or slower than
  its estimate gets a look before anything is built on it (training luck
  has already faked two passes, see `docs/decisions.md`).
- Pass or fail is not enough: dig into the raw outputs (per encounter, per
  HP band, per decision kind, stalls, timing) for why, write that into the
  results doc, and ask what the result changes about the plan.
- Goal-2 reads use the gauntlet protocol (`yardstick/protocol`): `--against`
  the control on the same sequences and setting; the headline setting and
  its control are `yardstick/headline-setting` and
  `yardstick/headline-control`. Report an effect at fixed n.
- Report by fight type (hallway, elite, boss) and keep train and held-out
  content apart; a single-seed pass is a lead, never a result.
- Promote a player only with `scripts/product.py set` (fact
  `product/net`).

## Filing facts (kb)

- `kb` is a shell function in Bash; in PowerShell it is `python -I
  $HOME/.claude/skills/kb/kb.py`.
- Before working a fact out from files, `kb find <words>`; `kb render` at
  start shows suspect facts and the index.
- Each read: `kb set measurement/<name> "<value>" --from <results-doc
  section as path#heading> <results file> jobs/done/<id>.json
  key:product/net key:yardstick/<...>`, all sources after one `--from`.
- Each decision: `kb set decision/<name> "..." --from
  "docs/decisions.md#<heading>"`. Re-set or retire facts a result changes.
- The steward files as `CLAUDE_CODE_SESSION_ID=steward-$CLAUDE_CODE_SESSION_ID
  kb set ... --note "steward: <job id>"`: kb records that id as `by`, so
  its filing never resets stagnation.
- A suspect fact is resolved (confirmed with what was checked, flagged,
  re-set or retired) by its owner: the lane worker for its lane's
  `measurement/` facts, the navigator for the rest and for closed lanes'.
  `health.py` turns `stale-facts` red after a day.
- One home per fact: elsewhere, write its key. Hand edits to `docs/claims/`
  are rejected at commit.
- A value is one claim of 400 characters or less (kb warns above), true
  now: no "was", no history (kb keeps old values). Longer text goes in a
  file the fact cites. Values may be terse and technical: agents read them.
- The curate task (app-scheduled, Sonnet, daily) follows
  `~/.claude/skills/curate/SKILL.md`: overdue suspect facts, duplicates,
  splits and long values, one area per run.

## Specs and builds

- Follow the owner's workflow by reading the skill files directly:
  `~/.claude/skills/spec/SKILL.md`, then `~/.claude/skills/build/SKILL.md`
  with its **Away rules** (section 5). Answer interview questions as the
  owner would from AGENTS.md, the memory notes, `docs/direction.md` and
  this file; confirm specs under the mandate.
- Use subagents, forks and workflows freely for independent parts.
- Decisions: decide, prefer the most reversible option, and record it in
  `docs/decisions.md` marked "(on the owner's behalf)" with the
  alternatives; the digest lists it. Never decide what the grants forbid:
  put it in the digest, and in an escalation if it blocks.

## Digest and escalations

- The steward writes `docs/digest/<date>.md` at its first run after 07:00
  (at most 60 lines; format in its prompt), commits and pushes it, and
  sends one push notification a day with its first line.
- An escalation is a notice, never a question: a separate push
  notification when a blocker stays red for 3 steward runs, or when only
  the owner can fix the problem (the app not running
  scheduled tasks, auth expired, disk full of data the grants forbid
  deleting).
